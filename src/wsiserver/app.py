from io import BytesIO
import math

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from PIL import Image
import openslide
from openslide.deepzoom import DeepZoomGenerator

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("wsi", type=str, help="path to the WSI to load")
parser.add_argument("--port", type=int, default=31791, help="port to listen on")
parser.add_argument("--tile_size", type=int, default=256, help="tile size")
args = parser.parse_args()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)
dzg = DeepZoomGenerator(
    openslide.OpenSlide(args.wsi),
    tile_size=args.tile_size,
    overlap=0,
    limit_bounds=False)
max_zoom = dzg.level_count - 1
min_zoom = int(max_zoom - math.log2(max(dzg.level_dimensions[-1])/args.tile_size))
default_zoom = min_zoom + 2
zoom2size = {
    i: {"x": dzg.level_dimensions[i][0], "y": dzg.level_dimensions[i][1]}
    for i in range(min_zoom, max_zoom + 1)}


@app.get("/props", response_model=dict)
def props():
    return {
        "tile_size": args.tile_size,
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "default_zoom": default_zoom,
        "bounds": dzg.level_dimensions[max_zoom],
        "zoom2size": zoom2size,
    }


@app.get("/tile/{level:int}/{x:int}/{y:int}", responses={
    200: {
        "content": {
            "image/png": {}
        }
    }
})
async def tile(x: int, y: int, level: int):
    if x < 0 or y < 0:
        return Response(content="", media_type="image/png")
    if dzg.level_tiles[level][0] <= x or dzg.level_tiles[level][1] <= y:
        return Response(content="", media_type="image/png")

    tile = dzg.get_tile(level, (x, y))
    if tile.size != (args.tile_size, args.tile_size):
        canvas = Image.new("RGBA", (args.tile_size, args.tile_size))
        canvas.paste(tile, (0, 0))
        tile = canvas
    buf = BytesIO()
    tile.save(buf, "png", quality=70)
    return Response(content=buf.getvalue(), media_type="image/png")


def main():
    uvicorn.run("wsiserver.app:app", host="0.0.0.0", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
