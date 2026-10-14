import os
import cv2
import numpy as np
from PIL import Image
import mediapipe as mp
try:
    from ai_edge_litert import interpreter as tflite
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite

FACE_OVAL_INDICES = [
    176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379,
    378, 400, 377, 152, 148
]

class FaceCutoutEngine:
    def __init__(self, model_dir=None):
        if model_dir is None:
            model_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.multiclass_model_path = os.path.join(model_dir, 'selfie_multiclass_256x256.tflite')
        self.mp_face_mesh = mp.solutions.face_mesh
        self._interp = None
        self._init_tflite()

    def _init_tflite(self):
        if os.path.exists(self.multiclass_model_path):
            try:
                self._interp = tflite.Interpreter(model_path=self.multiclass_model_path)
                self._interp.allocate_tensors()
                self._input_details = self._interp.get_input_details()
                self._output_details = self._interp.get_output_details()
            except Exception as e:
                print(f"Warning: Failed to load multiclass tflite: {e}")
                self._interp = None

    def get_hair_mask(self, img_bgr):
        """Extracts hair segmentation mask using multiclass model (0~255)."""
        if self._interp is None:
            return np.zeros((img_bgr.shape[0], img_bgr.shape[1]), dtype=np.uint8)
        
        h, w, _ = img_bgr.shape
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (256, 256), interpolation=cv2.INTER_LINEAR)
        input_data = np.expand_dims(resized.astype(np.float32) / 255.0, axis=0)

        self._interp.set_tensor(self._input_details[0]['index'], input_data)
        self._interp.invoke()
        logits = self._interp.get_tensor(self._output_details[0]['index'])[0]

        exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

        # Class 1 is hair
        hair_prob = probs[:, :, 1]
        hair_mask_256 = (hair_prob > 0.35).astype(np.uint8) * 255
        hair_mask = cv2.resize(hair_mask_256, (w, h), interpolation=cv2.INTER_LINEAR)
        return hair_mask

    def get_face_mesh_mask(self, img_bgr, scale_factor=1.0):
        """Extracts face mask using FaceMesh with optional scale expansion."""
        h, w, _ = img_bgr.shape
        rgb_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        with self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=10,
            refine_landmarks=True,
            min_detection_confidence=0.5
        ) as face_mesh:
            results = face_mesh.process(rgb_img)

        if not results.multi_face_landmarks:
            return np.zeros((h, w), dtype=np.uint8), 0

        num_faces = len(results.multi_face_landmarks)
        base_mask = np.zeros((h, w), dtype=np.uint8)

        for face_landmarks in results.multi_face_landmarks:
            raw_pts = []
            for idx in FACE_OVAL_INDICES:
                lm = face_landmarks.landmark[idx]
                x = lm.x * w
                y = lm.y * h
                raw_pts.append([x, y])
            
            raw_pts = np.array(raw_pts, dtype=np.float32)
            
            if scale_factor != 1.0:
                center = np.mean(raw_pts, axis=0)
                expanded_pts = center + (raw_pts - center) * scale_factor
                pts = np.clip(expanded_pts, 0, [w - 1, h - 1]).astype(np.int32)
            else:
                pts = raw_pts.astype(np.int32)

            cv2.fillPoly(base_mask, [pts], 255)

        return base_mask, num_faces

    def get_bounding_boxes(self, mask, padding=0):
        """Returns list of [x1, y1, x2, y2] bounding boxes from mask contours."""
        boxes = []
        if not np.any(mask > 0):
            return boxes
        h, w = mask.shape[:2]
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            if cv2.contourArea(c) < 50:
                continue
            bx, by, bw, bh = cv2.boundingRect(c)
            pad = max(0, int(padding))
            x1 = max(0, bx - pad)
            y1 = max(0, by - pad)
            x2 = min(w, bx + bw + pad)
            y2 = min(h, by + bh + pad)
            boxes.append([x1, y1, x2, y2])
        return boxes

    def create_mask(self, img_bgr, mode="face_only", shape="contour", expand_pixels=0, feather_radius=5, scale_factor=1.0):
        h, w, _ = img_bgr.shape
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        num_faces = 0

        if mode in ("face_only", "face_hair"):
            face_mask, num_faces = self.get_face_mesh_mask(img_bgr, scale_factor=scale_factor)
            combined_mask = cv2.bitwise_or(combined_mask, face_mask)

        if mode in ("face_hair", "hair_only"):
            hair_mask = self.get_hair_mask(img_bgr)
            combined_mask = cv2.bitwise_or(combined_mask, hair_mask)
            if num_faces == 0 and np.any(hair_mask > 0):
                num_faces = 1

        if shape == "box" and np.any(combined_mask > 0):
            box_mask = np.zeros((h, w), dtype=np.uint8)
            boxes = self.get_bounding_boxes(combined_mask, padding=expand_pixels)
            for x1, y1, x2, y2 in boxes:
                cv2.rectangle(box_mask, (x1, y1), (x2, y2), 255, -1)
            combined_mask = box_mask
        else:
            if expand_pixels > 0:
                kernel_size = int(expand_pixels) * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                combined_mask = cv2.dilate(combined_mask, kernel)
            elif expand_pixels < 0:
                kernel_size = abs(int(expand_pixels)) * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                combined_mask = cv2.erode(combined_mask, kernel)

        if feather_radius > 0:
            ksize = int(feather_radius) * 2 + 1
            final_mask = cv2.GaussianBlur(combined_mask, (ksize, ksize), 0)
        else:
            final_mask = combined_mask

        return final_mask, num_faces

    def apply_fill_to_mask(self, img_bgr, mask, fill_type="transparent"):
        """Applies fill (transparent, white, black) using the provided mask."""
        if fill_type == "transparent":
            alpha = 255 - mask
            b, g, r = cv2.split(img_bgr)
            result = cv2.merge([b, g, r, alpha])
        elif fill_type == "white":
            alpha_f = (mask.astype(np.float32) / 255.0)[:, :, np.newaxis]
            white_col = np.array([255, 255, 255], dtype=np.float32)
            res_f = img_bgr.astype(np.float32) * (1.0 - alpha_f) + white_col * alpha_f
            result = np.clip(res_f, 0, 255).astype(np.uint8)
        elif fill_type == "black":
            alpha_f = (mask.astype(np.float32) / 255.0)[:, :, np.newaxis]
            black_col = np.array([0, 0, 0], dtype=np.float32)
            res_f = img_bgr.astype(np.float32) * (1.0 - alpha_f) + black_col * alpha_f
            result = np.clip(res_f, 0, 255).astype(np.uint8)
        else:
            result = img_bgr.copy()
        return result

    def process_image(self, img_bgr, mode="face_only", shape="contour", fill_type="transparent", 
                      expand_pixels=0, feather_radius=5, scale_factor=1.0):
        mask, num_faces = self.create_mask(
            img_bgr, mode=mode, shape=shape, expand_pixels=expand_pixels, 
            feather_radius=feather_radius, scale_factor=scale_factor
        )
        result = self.apply_fill_to_mask(img_bgr, mask, fill_type=fill_type)
        return result, mask, num_faces

    def process_file(self, input_path, output_path, mode="face_only", shape="contour", 
                     fill_type="transparent", expand_pixels=0, feather_radius=5, scale_factor=1.0):
        img_bgr = cv2.imread(input_path)
        if img_bgr is None:
            raise ValueError(f"Could not read image: {input_path}")
        
        result, mask, num_faces = self.process_image(
            img_bgr, mode=mode, shape=shape, fill_type=fill_type, 
            expand_pixels=expand_pixels, feather_radius=feather_radius, scale_factor=scale_factor
        )
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cv2.imwrite(output_path, result)
        return num_faces
