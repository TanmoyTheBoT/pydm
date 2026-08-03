from pathlib import Path
from urllib.parse import urlparse
import re

import httpx


def get_filename(response: httpx.Response, original_url: str) -> str:
    """
    Get filename from download response.

    Priority:
    1. Content-Disposition
    2. Redirected URL
    3. Original URL
    4. download.bin
    """

    content_disposition = response.headers.get("Content-Disposition")

    if content_disposition:
        match = re.search(
            r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
            content_disposition
        )

        if match:
            return Path(match.group(1)).name


    # Final redirected URL
    final_name = Path(
        urlparse(str(response.url)).path
    ).name

    if final_name:
        return final_name


    # Original URL
    original_name = Path(
        urlparse(original_url).path
    ).name

    if original_name:
        return original_name


    return "download.bin"



def download_file(url: str, output_dir: str = None):
    """
    Download file.

    Returns:
        saved file path
    """

    if output_dir is None:
        output_dir = str(Path.home() / "Downloads")

    output_path = Path(output_dir)
    output_path.mkdir(
        parents=True,
        exist_ok=True
    )


    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=None,
    ) as response:


        response.raise_for_status()


        filename = get_filename(
            response,
            url
        )


        save_path = output_path / filename


        total_size = int(
            response.headers.get(
                "Content-Length",
                0
            )
        )


        downloaded = 0


        with open(
            save_path,
            "wb"
        ) as file:


            for chunk in response.iter_bytes(
                chunk_size=1024 * 64
            ):

                if chunk:

                    file.write(chunk)

                    downloaded += len(chunk)


                    yield {
                        "downloaded": downloaded,
                        "total": total_size,
                        "filename": filename,
                        "path": str(save_path),
                    }


    yield {
        "completed": True,
        "filename": filename,
        "path": str(save_path),
    }