import bpy
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "static" / "nanbudangan" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, color, metallic=0.0, roughness=0.55):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return material


BLACK = mat("Hull black", (0.018, 0.026, 0.029), 0.22, 0.38)
RED = mat("Oxide red", (0.31, 0.055, 0.035), 0.1, 0.48)
IVORY = mat("Aged ivory", (0.64, 0.61, 0.52), 0.02, 0.58)
WOOD = mat("Wet teak", (0.20, 0.125, 0.072), 0.0, 0.66)
BRASS = mat("Brass", (0.34, 0.20, 0.055), 0.72, 0.28)
GLASS = mat("Dark glass", (0.008, 0.035, 0.045), 0.5, 0.16)
STEEL = mat("Dark steel", (0.075, 0.09, 0.095), 0.75, 0.3)
CANVAS = mat("Lifeboat canvas", (0.72, 0.67, 0.53), 0.0, 0.77)


def smooth(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True


def bevel(obj, width=0.18, segments=3):
    mod = obj.modifiers.new("Soft ship edges", "BEVEL")
    mod.width = width
    mod.segments = segments


def cube(name, loc, scale, material, bevel_width=0.12):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (scale[0] / 2, scale[1] / 2, scale[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel_width:
        bevel(obj, bevel_width, 3)
    return obj


def cylinder(name, loc, radius, depth, material, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    bevel(obj, min(radius * .09, .16), 2)
    smooth(obj)
    return obj


def curve_tube(name, points, radius, material, cyclic=False):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (*co, 1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def hull_mesh():
    # Dense longitudinal stations form a closed displacement hull. Each station
    # runs from port deck edge, under the keel, to starboard deck edge.
    xs = [-72 + i * 1.5 for i in range(97)]
    verts, faces = [], []
    rings = 17
    for x in xs:
        q = (x + 72) / 144
        stern_fine = math.sin(math.pi * min(q / .15, 1) / 2) if q < .15 else 1
        bow_fine = math.sin(math.pi * min((1 - q) / .20, 1) / 2) if q > .80 else 1
        fullness = max(.012, stern_fine * bow_fine)
        half_width = 10.5 * (fullness ** .42)
        sheer = .45 + 1.15 * ((abs(q - .48) / .52) ** 2)
        deck_z = 12.8 + sheer
        keel_z = -3.9 + .7 * ((abs(q - .5) / .5) ** 2)
        for j in range(rings):
            t = j / (rings - 1)
            angle = math.pi * t
            y = -half_width * math.cos(angle)
            rise = abs(math.cos(angle)) ** .43
            z = keel_z + (deck_z - keel_z) * rise
            # Fine V at the keel; broad, almost vertical upper sides.
            if .28 < t < .72:
                y *= .82 + .18 * abs(math.cos(angle))
            # The upper bow overhangs the waterline and gives the stem a rake.
            x_offset = 0
            if q > .82:
                height_ratio = (z - keel_z) / max(deck_z - keel_z, .1)
                x_offset = (q - .82) / .18 * height_ratio * 3.5
            # Elliptical cruiser stern rather than a square transom.
            if q < .12:
                x_offset -= (1 - q / .12) * ((z - keel_z) / max(deck_z - keel_z, .1)) * 1.3
            verts.append((x + x_offset, y, z))
    for i in range(len(xs) - 1):
        for j in range(rings - 1):
            a = i * rings + j
            faces.append((a, a + rings, a + rings + 1, a + 1))
        # Close the weather deck between the two sheer edges.
        a = i * rings
        b = (i + 1) * rings
        faces.append((a, a + rings - 1, b + rings - 1, b))
    faces.append(tuple(range(rings - 1, -1, -1)))
    end = (len(xs) - 1) * rings
    faces.append(tuple(end + j for j in range(rings)))
    mesh = bpy.data.meshes.new("Nanan hull curved mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("NAN AN - sculpted hull", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(BLACK)
    smooth(obj)
    bevel(obj, .13, 2)
    return obj


hull_mesh()
# Hull bands and deck lips emphasize scale and curvature.
curve_tube("Red waterline", [(-64, 10.0, 5.0), (-45, 10.15, 5.0), (0, 10.3, 5.0), (45, 9.8, 5.1), (64, 5.6, 5.5)], .15, RED)
curve_tube("White sheer line", [(-65, 7.0, 12.7), (-35, 10.0, 13.6), (5, 10.3, 13.8), (46, 9.4, 13.4), (66, 3.2, 12.0)], .12, IVORY)
cube("Promenade deck", (0, 0, 14.2), (116, 19.2, .75), WOOD, .25)
cube("Lower superstructure", (-5, 0, 17.0), (94, 16.4, 5.0), IVORY, .48)
cube("Upper superstructure", (-1, 0, 21.4), (70, 14.2, 4.0), IVORY, .42)
cube("Boat deck", (0, 0, 24.0), (79, 15.3, .65), WOOD, .2)
cube("Bridge house", (39, 0, 20.0), (16, 15.7, 8.4), IVORY, .5)
cube("Bridge wing", (42, 0, 23.4), (10, 20.2, 2.1), IVORY, .35)
cube("Forward observation deck", (52, 0, 16.5), (18, 13.5, 3.2), IVORY, .42)

# Window strips with brass surrounds.
for side in (-1, 1):
    y = side * 8.25
    for z, start, end, step in [(17.4, -45, 31, 4.8), (21.5, -32, 31, 4.4)]:
        for x in [start + i * step for i in range(int((end - start) / step) + 1)]:
            cylinder("Brass window rim", (x, y, z), .47, .13, BRASS, 24, (math.pi / 2, 0, 0))
            cylinder("Black window glass", (x, y + side * .08, z), .35, .15, GLASS, 24, (math.pi / 2, 0, 0))
    for x in (36, 40, 44, 48):
        cube("Bridge window", (x, side * 8.02, 21.3), (2.3, .16, 1.25), GLASS, .16)

# Four classic raked funnels with black caps, rims, stays and pale bases.
for index, x in enumerate((-28.5, -9.5, 9.5, 28.5), 1):
    base = cylinder(f"Funnel {index} base", (x, 0, 25.3), 4.25, 2.0, IVORY, 40)
    funnel = cylinder(f"Funnel {index}", (x, 0, 32.7), 3.45, 13.3, RED, 48)
    funnel.scale = (.84, 1, 1)
    funnel.rotation_euler[1] = math.radians(-3.5)
    cap = cylinder(f"Funnel {index} black cap", (x - .38, 0, 38.1), 3.48, 3.4, BLACK, 48)
    cap.scale = (.84, 1, 1)
    cap.rotation_euler[1] = math.radians(-3.5)
    curve_tube(f"Funnel {index} rim", [(x - .62, 0, 39.85)], .0, STEEL)
    for side in (-1, 1):
        curve_tube(f"Funnel {index} stay", [(x, side * 2.8, 25), (x - .55, side * 3.1, 38)], .055, STEEL)

# Railings: multiple horizontal runs and regularly spaced stanchions.
for level, half_width, start, end in [(14.9, 9.65, -57, 57), (24.7, 7.7, -38, 39)]:
    for side in (-1, 1):
        y = side * half_width
        curve_tube("Rail top", [(start, y, level + 1), (end, y, level + 1)], .055, STEEL)
        curve_tube("Rail middle", [(start, y, level + .52), (end, y, level + .52)], .035, STEEL)
        for x in range(start, end + 1, 3):
            curve_tube("Rail stanchion", [(x, y, level), (x, y, level + 1.05)], .045, STEEL)

# Lifeboats, davits and deck ventilators.
for side in (-1, 1):
    for x in (-43, -32, 34, 45):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=12, location=(x, side * 7.0, 25.5), scale=(3.6, 1.18, .82))
        boat = bpy.context.object
        boat.name = "Covered lifeboat"
        boat.data.materials.append(CANVAS)
        smooth(boat)
        for dx in (-2.3, 2.3):
            curve_tube("Lifeboat davit", [(x + dx, side * 5.9, 24.3), (x + dx, side * 8.0, 28.0)], .09, STEEL)
for x in (-39, 39):
    cylinder("Ventilator trunk", (x, 3.1, 26.1), .65, 3.2, IVORY, 24)
    curve_tube("Ventilator cowl", [(x, 3.1, 27.6), (x, 4.1, 28.3), (x, 4.8, 27.7)], .62, IVORY)

# Fore and aft masts, yards and rigging.
for x, height in [(-50, 20), (50, 18)]:
    cylinder("Tapered mast", (x, 0, 25 + height / 2), .22, height, STEEL, 16)
    curve_tube("Yardarm", [(x, -7, 36), (x, 7, 36)], .1, STEEL)
    for side in (-1, 1):
        curve_tube("Mast rigging", [(x, 0, 44), (x - 10, side * 8, 24.5)], .035, STEEL)

# Anchor and hawse pipes on the bow.
for side in (-1, 1):
    cylinder("Hawse pipe", (58.5, side * 5.6, 10.1), .68, .25, STEEL, 28, (math.pi / 2, 0, 0))
    curve_tube("Anchor stock", [(59, side * 6.1, 9), (59, side * 7.4, 6.8)], .15, STEEL)

# Name plates on both bows (geometry plate; text remains legible in close shots later).
for side in (-1, 1):
    cube("NAN AN name plate", (51, side * 7.35, 11.8), (9.5, .12, 1.15), BRASS, .12)

# Save editable source and export a compact web model.
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "blender" / "nanan_ship.blend"))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(
    filepath=str(MODEL_DIR / "nanan_ship.glb"),
    export_format="GLB",
    export_apply=True,
    export_yup=True,
    export_materials="EXPORT",
)

# A neutral preview render for visual QA.
bpy.ops.object.camera_add(location=(102, -118, 55))
camera = bpy.context.object
bpy.context.scene.camera = camera
direction = Vector((0, 0, 19)) - camera.location
camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
camera.data.lens = 58
bpy.ops.object.light_add(type="AREA", location=(30, -45, 75))
bpy.context.object.data.energy = 2300
bpy.context.object.data.shape = "DISK"
bpy.context.object.data.size = 55
bpy.ops.object.light_add(type="AREA", location=(-55, 30, 35))
bpy.context.object.data.energy = 900
bpy.context.object.data.size = 40
world = bpy.context.scene.world or bpy.data.worlds.new("Preview world")
bpy.context.scene.world = world
world.color = (.055, .07, .075)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(ROOT / "blender" / "nanan_ship_preview.png")
bpy.ops.render.render(write_still=True)
