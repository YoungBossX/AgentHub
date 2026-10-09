"""Isolated, bounded attachment decoder. No network, shell or file paths as input."""

import base64
import io
import json
import sys
import warnings

MAX_BYTES = 8 * 1024 * 1024
MAX_TEXT = 60_000


def decode(kind: str, data: bytes) -> dict:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("附件为空或超过 8 MiB。")
    if kind == "text":
        if len(data) > 512 * 1024:
            raise ValueError("文本文件不能超过 512 KiB。")
        text = data.decode("utf-8-sig", errors="strict")
        if any(ord(c) < 32 and c not in "\t\r\n" for c in text):
            raise ValueError("文件包含二进制控制字符，请提供 UTF-8 文本。")
        return {"kind": kind, "media_type": "text/plain", "text_content": text[:MAX_TEXT],
                "text_truncated": len(text) > MAX_TEXT, "extraction_status": "ready" if text.strip() else "no_text"}
    if kind == "pdf":
        from pypdf import PdfReader, apply_configuration

        if not data.startswith(b"%PDF-"):
            raise ValueError("文件内容不是 PDF。")
        with apply_configuration(
            maximum_declared_stream_length=16 * 1024 * 1024,
            zlib_maximum_output_length=16 * 1024 * 1024,
            lzw_maximum_output_length=16 * 1024 * 1024,
            run_length_maximum_output_length=16 * 1024 * 1024,
            array_based_stream_maximum_output_length=16 * 1024 * 1024,
            page_tree_maximum_entries=1000, page_tree_maximum_depth=50,
            xform_maximum_invocations_per_extraction=1000,
        ):
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ValueError("暂不支持加密 PDF，请先解密后上传。")
            if len(reader.pages) > 100:
                raise ValueError("PDF 不能超过 100 页，请先拆分文档。")
            parts, length, truncated = [], 0, False
            for index, page in enumerate(reader.pages):
                extracted = page.extract_text() or ""
                extracted = "".join(c for c in extracted if ord(c) >= 32 or c in "\t\r\n")
                text = f"[第 {index + 1} 页]\n{extracted}\n"
                remaining = MAX_TEXT - length
                parts.append(text[:remaining])
                length += min(len(text), remaining)
                if len(text) > remaining or length == MAX_TEXT and index + 1 < len(reader.pages):
                    truncated = True
                    break
            content = "".join(parts)
            # Page labels alone are not extracted document content.
            has_text = any(line.strip() and not line.startswith("[第 ") for line in content.splitlines())
            return {"kind": kind, "media_type": "application/pdf", "text_content": content if has_text else "",
                    "text_truncated": truncated, "extraction_status": "ready" if has_text else "no_text"}
    if kind == "image":
        from PIL import Image, ImageOps

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["PNG", "JPEG", "WEBP"]) as source:
                width, height = source.size
                if width * height > 12_000_000 or max(width, height) > 10_000:
                    raise ValueError("图片不能超过 1200 万像素或单边 10000 像素。")
                if getattr(source, "n_frames", 1) != 1:
                    raise ValueError("暂不支持动画图片，请上传静态截图。")
                media = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[source.format]
                source.verify()
            with Image.open(io.BytesIO(data), formats=["PNG", "JPEG", "WEBP"]) as source:
                oriented = ImageOps.exif_transpose(source).convert("RGBA")
                normalized = Image.new("RGB", oriented.size, "white")
                normalized.paste(oriented, mask=oriented.getchannel("A"))
                normalized.thumbnail((2048, 2048))
                output = io.BytesIO()
                normalized.save(output, format="JPEG", quality=90)
            image = output.getvalue()
            if len(image) > 4 * 1024 * 1024:
                raise ValueError("图片处理后仍过大，请缩小图片。")
        return {"kind": kind, "media_type": media, "extraction_status": "image",
                "image_width": width, "image_height": height, "image_media_type": "image/jpeg",
                "image_base64": base64.b64encode(image).decode("ascii")}
    raise ValueError("不支持此文件类型。")


if __name__ == "__main__":
    try:
        result = decode(sys.argv[1], sys.stdin.buffer.read(MAX_BYTES + 1))
        print(json.dumps({"ok": True, "value": result}, ensure_ascii=True))
    except Exception as exc:
        # Return a bounded diagnostic, never a traceback containing host paths.
        reason = str(exc) if isinstance(exc, (ValueError, UnicodeDecodeError)) else "文件无法解析，请检查格式或重新导出。"
        print(json.dumps({"ok": False, "error": reason[:300]}, ensure_ascii=True))
        sys.exit(1)
