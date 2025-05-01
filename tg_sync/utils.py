import aiofiles
import os.path
import yaml

async def save_yaml(data, path):
    async with aiofiles.open(path, "w") as file:
        await file.write(yaml.dump(data))
        await file.flush()

def get_uniq_path(file_path: str) -> str:
    (base, ext) = os.path.splitext(file_path)
    count = 1
    while os.path.exists(file_path):
        count += 1
        file_path = f"{base} ({count}){ext}"
    return file_path
