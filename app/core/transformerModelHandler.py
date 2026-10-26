import numpy as np
from sentence_transformers import CrossEncoder
import gc
import torch
from transformers import AutoModel, AutoProcessor


class TransformerHandler:
    def __init__(self, cross_encoder: str = "cross-encoder/nli-deberta-v3-large", siglip_model: str = "google/siglip2-base-patch16-naflex"):
        self.cross_encoder = CrossEncoder(cross_encoder, device="cuda")
        self.cross_encoder.labels = ["contradiction", "entailment", "uncertain"]
        self.cross_encoder_offload()

        self.siglip_model = AutoModel.from_pretrained(siglip_model, device_map="auto", attn_implementation="sdpa")
        self.siglip_processor = AutoProcessor.from_pretrained(siglip_model)
        self.siglip_model_offload()

    def cross_encoder_offload(self):
        self.cross_encoder.to("cpu")
        gc.collect()
        torch.cuda.empty_cache()

    def siglip_model_offload(self):
        self.siglip_model.to("cpu")
        gc.collect()
        torch.cuda.empty_cache()

    def ask_Siglip_Model(self, texts, image) -> list:
        if self.siglip_model.device == "cpu":
            self.siglip_model.to("cuda")

        inputs = self.siglip_processor(text=texts, images=image, padding="max_length", return_tensors="pt").to(self.siglip_model.device)

        with torch.no_grad():
            outputs = self.siglip_model(**inputs)

        logits_per_image = outputs.logits_per_image
        probs = torch.sigmoid(logits_per_image)
        scores = [round(p, 4) for p in probs[0].tolist()]

        return scores

    def ask_cross_encoder(self, pairs):
        if self.cross_encoder.device == "cpu":
            self.cross_encoder.to("cuda")

        raw_scores = self.cross_encoder.predict(pairs)

        if raw_scores.ndim == 1:
            raw_scores = np.expand_dims(raw_scores, axis=0)

        return raw_scores