"""
Generate scripts/atlas-world-geometry.json for the World Trust Atlas preview.

Natural Earth 110m land polygons, clipped to [-180, 180] x [-58, 82]
(no Antarctica), projected to Robinson, scaled to a 980-unit-wide viewBox.
City pins are projected the same way so they land exactly on the map.

    python scripts/make_atlas_world_geometry.py
"""

import json

import cartopy.crs as ccrs
import cartopy.feature as cfeature
from shapely.geometry import Polygon, box

PROJ = ccrs.Robinson()
PC = ccrs.PlateCarree()
CLIP = box(-180, -58, 180, 82)
WIDTH = 980.0
MIN_AREA = 8e9  # m^2 in Robinson units — drops specks, keeps real islands

CITIES = {
    "New York": (40.713, -74.006),
    "Miami": (25.762, -80.192),
    "Mexico City": (19.433, -99.133),
    "Sao Paulo": (-23.551, -46.633),
    "Lagos": (6.524, 3.379),
    "Nairobi": (-1.286, 36.817),
    "Cape Town": (-33.925, 18.424),
    "Mumbai": (19.076, 72.878),
    "Singapore": (1.352, 103.820),
    "Jakarta": (-6.208, 106.846),
    "Tokyo": (35.677, 139.650),
    "Sydney": (-33.869, 151.209),
}


def main() -> None:
    land = cfeature.NaturalEarthFeature("physical", "land", "110m")
    polys = []
    for geom in land.geometries():
        clipped = geom.intersection(CLIP)
        if clipped.is_empty:
            continue
        projected = PROJ.project_geometry(clipped, PC)
        parts = [projected] if isinstance(projected, Polygon) else list(projected.geoms)
        polys.extend(p for p in parts if isinstance(p, Polygon) and p.area >= MIN_AREA)

    xs, ys = [], []
    for p in polys:
        bx = p.bounds
        xs.extend([bx[0], bx[2]])
        ys.extend([bx[1], bx[3]])
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    s = WIDTH / (x1 - x0)
    height = round((y1 - y0) * s, 1)

    def pt(x, y):
        return round((x - x0) * s, 1), round((y1 - y) * s, 1)

    paths = []
    for p in sorted(polys, key=lambda g: -g.area):
        coords = list(p.exterior.coords)
        d = []
        for i, (x, y) in enumerate(coords):
            px, py = pt(x, y)
            d.append(("M" if i == 0 else "L") + f"{px},{py}")
        paths.append("".join(d) + "Z")

    pins = {}
    for name, (lat, lon) in CITIES.items():
        gx, gy = PROJ.transform_point(lon, lat, PC)
        px, py = pt(gx, gy)
        pins[name] = [px, py]

    out = {"w": WIDTH, "h": height, "paths": paths, "pins": pins}
    with open("scripts/atlas-world-geometry.json", "w", encoding="utf-8") as f:
        json.dump(out, f)
    size = len(json.dumps(out)) / 1024
    print(f"atlas-world-geometry.json: {len(paths)} paths, {len(pins)} pins, "
          f"{WIDTH:.0f}x{height} viewBox, {size:.0f} KB")


if __name__ == "__main__":
    main()
