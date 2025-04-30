import aiofiles
import yaml

async def save_yaml(data, path):
    async with aiofiles.open(path, "w") as file:
        await file.write(yaml.dump(data))
        await file.flush()
