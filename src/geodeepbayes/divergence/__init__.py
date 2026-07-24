"""分布距离估计: k-NN(KSG) KL 估计器与边际平均直方图 KL（对照）。"""
from .knn_kl import knn_kl_divergence
from .histogram_kl import histogram_kl_divergence

__all__ = ["knn_kl_divergence", "histogram_kl_divergence"]
