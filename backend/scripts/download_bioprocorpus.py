#!/usr/bin/env python
"""下载 BioProCorpus 协议语料库到 backend/data/bioprocorpus/。

大文件（约 514MB）不进 git / 不进 Docker 镜像。部署时若需要「协议推荐 / 文献推荐」
功能，在容器启动期调用本脚本按需拉取。

数据源（二选一，通过环境变量提供）：
  DATASET_BASE_URL   某可直链下载的 URL（S3 / Supabase Storage / GitHub Release / 对象存储）。
                     若指向 .tar.gz / .zip 会自动解压；否则按目录递归下载（需以 / 结尾）。
  HF_DATASET_REPO    形如 "user/dataset"（Hugging Face datasets），用 huggingface_hub 拉取。

输出目录：backend/data/bioprocorpus/（与 BIOPROCORPUS_DIR 默认路径一致）

用法：
  DATASET_BASE_URL=https://my-bucket.s3.amazonaws.com/bioprocorpus/ python scripts/download_bioprocorpus.py
  HF_DATASET_REPO=myuser/bioprocorpus python scripts/download_bioprocorpus.py

无以上变量时脚本直接退出（不下载），对应功能在缺数据时静默降级为空结果。
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("download_bioprocorpus")

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(HERE)
DEFAULT_DIR = os.path.join(BACKEND_DIR, "data", "bioprocorpus")
# 优先使用 BIOPROCORPUS_DIR，使其与运行时加载路径（protocol_recommender.py）一致：
# 无论「一次性上传到持久盘」还是「启动期下载」，写盘与读盘都指向同一目录。
TARGET_DIR = os.environ.get("BIOPROCORPUS_DIR", DEFAULT_DIR)


def main() -> int:
    base_url = os.environ.get("DATASET_BASE_URL", "").rstrip("/")
    hf_repo = os.environ.get("HF_DATASET_REPO", "").strip()

    if not base_url and not hf_repo:
        logger.info("未设置 DATASET_BASE_URL / HF_DATASET_REPO，跳过下载（功能将降级为空结果）。")
        return 0

    os.makedirs(TARGET_DIR, exist_ok=True)

    # 目标目录非空则跳过，避免重复下载
    if os.listdir(TARGET_DIR):
        logger.info("目标目录非空，跳过下载：%s", TARGET_DIR)
        return 0

    if hf_repo:
        return _download_from_hf(hf_repo)
    return _download_from_url(base_url)


def _download_from_hf(repo: str) -> int:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        logger.error("未安装 huggingface_hub，无法用 HF_DATASET_REPO 下载。请 pip install huggingface_hub。")
        return 1
    logger.info("从 Hugging Face dataset 拉取：%s -> %s", repo, TARGET_DIR)
    try:
        snapshot_download(repo_id=repo, repo_type="dataset", local_dir=TARGET_DIR)
        logger.info("下载完成。")
        return 0
    except Exception as e:  # noqa: BLE001
        logger.error("HF 下载失败：%s", e)
        return 1


def _download_from_url(base_url: str) -> int:
    import shutil
    import tarfile
    import zipfile
    import urllib.request

    if base_url.endswith((".tar.gz", ".tgz", ".zip")):
        archive_name = os.path.basename(base_url)
        archive_path = os.path.join(TARGET_DIR, archive_name)
        logger.info("下载压缩包：%s", base_url)
        try:
            with urllib.request.urlopen(base_url) as resp:  # nosec - 用户自管 URL
                with open(archive_path, "wb") as f:
                    shutil.copyfileobj(resp, f)
        except Exception as e:  # noqa: BLE001
            logger.error("下载失败：%s", e)
            return 1
        logger.info("解压：%s", archive_path)
        if archive_path.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_path) as tf:
                tf.extractall(TARGET_DIR)
        else:
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(TARGET_DIR)
        os.remove(archive_path)
        logger.info("解压完成。")
        return 0

    # 目录递归下载（base_url 以 / 结尾，约定包含 manifest.txt 列出文件）
    manifest_url = base_url + "/manifest.txt"
    try:
        with urllib.request.urlopen(manifest_url) as resp:  # nosec
            files = [ln.decode().strip() for ln in resp.read().splitlines() if ln.strip()]
    except Exception:  # noqa: BLE001
        logger.error("未找到 manifest.txt，且非压缩包；请改用 .tar.gz 直链或 HF_DATASET_REPO。")
        return 1
    for fname in files:
        url = base_url + "/" + fname
        dst = os.path.join(TARGET_DIR, fname)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        logger.info("下载 %s", fname)
        try:
            with urllib.request.urlopen(url) as resp:  # nosec
                with open(dst, "wb") as f:
                    shutil.copyfileobj(resp, f)
        except Exception as e:  # noqa: BLE001
            logger.error("下载 %s 失败：%s", fname, e)
            return 1
    logger.info("目录下载完成，共 %d 个文件。", len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
