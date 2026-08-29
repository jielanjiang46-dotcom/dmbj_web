import bpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "nanbudangan" / "models" / "nanan_interiors.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, color, metallic=0.0, roughness=.58, emission=None):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = 2.5
    return mat


STEEL = material("Painted steel", (.16, .19, .19), .36, .48)
DARK_STEEL = material("Structural steel", (.045, .06, .065), .62, .36)
RUST = material("Oxidized fittings", (.31, .105, .052), .18, .74)
WOOD = material("Dark mahogany", (.19, .085, .035), .04, .4)
LIGHT_WOOD = material("Oak panels", (.43, .27, .12), .02, .45)
IVORY = material("First class ivory", (.73, .7, .6), .02, .5)
BRASS = material("Polished brass", (.47, .28, .06), .82, .2)
GLASS = material("Smoked glass", (.018, .07, .085), .34, .14)
FABRIC = material("Burgundy fabric", (.25, .025, .025), 0, .78)
LINEN = material("Used linen", (.52, .49, .4), 0, .88)
CARPET = material("First class carpet", (.23, .035, .028), 0, .92)
LAMP = material("Warm lamp", (.65, .42, .14), .1, .3, (1.0, .48, .12))


def cube(name, loc, scale, mat, bevel=.05):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = tuple(v / 2 for v in scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("Edge wear", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def cylinder(name, loc, radius, depth, mat, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def room_shell(prefix, origin, width, length, height, wall_mat, floor_mat):
    x, y, z = origin
    cube(prefix + " floor", (x, y, z), (width, length, .25), floor_mat)
    cube(prefix + " ceiling", (x, y, z + height), (width, length, .22), wall_mat)
    cube(prefix + " left wall", (x - width / 2, y, z + height / 2), (.22, length, height), wall_mat)
    cube(prefix + " right wall", (x + width / 2, y, z + height / 2), (.22, length, height), wall_mat)
    cube(prefix + " far bulkhead", (x, y - length / 2, z + height / 2), (width, .22, height), wall_mat)


def lamp(loc, scale=.18):
    cylinder("Brass lamp base", loc, scale * 1.35, .08, BRASS, (1.5708, 0, 0))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, location=(loc[0], loc[1] + .08, loc[2]), scale=(scale, .1, scale))
    bpy.context.object.data.materials.append(LAMP)


# Zone 1: third-class forward compartment, cramped and mechanically exposed.
O1 = (0, 0, 0)
room_shell("Third class", O1, 8.2, 21, 4.5, STEEL, DARK_STEEL)
for y in (-7.5, -3, 1.5, 6):
    for side in (-1, 1):
        x = side * 3.05
        for z in (1.0, 2.45):
            cube("Iron bunk frame", (x, y, z), (1.65, 3.25, .12), DARK_STEEL, .02)
            cube("Thin bunk mattress", (x, y, z + .14), (1.5, 3.0, .16), LINEN, .08)
        for dx in (-.76, .76):
            cylinder("Bunk upright", (x + dx, y, 1.75), .045, 3.15, DARK_STEEL)
for side in (-1, 1):
    cylinder("Steam pipe", (side * 3.75, 0, 3.75), .12, 20, RUST, (1.5708, 0, 0))
for y in (-7, -1, 5):
    lamp((0, y, 4.18), .22)
for y in (-5.2, 3.4):
    cube("Passenger trunk", (.65, y, .48), (1.45, .85, .7), WOOD, .11)

# Zone 2: second-class corridor, respectable but narrow.
O2 = (35, 0, 0)
room_shell("Second class", O2, 5.4, 23, 4.8, IVORY, LIGHT_WOOD)
cube("Second class runner", (35, 0, .15), (2.0, 22, .08), FABRIC, .01)
for y in (-8.5, -4.2, .1, 4.4, 8.7):
    for side in (-1, 1):
        x = 35 + side * 2.58
        cube("Cabin door", (x, y, 2.25), (.15, 2.25, 3.75), WOOD, .08)
        cylinder("Door knob", (x - side * .1, y + .65, 2.15), .09, .18, BRASS, (0, 1.5708, 0))
for y in (-7, -2.3, 2.4, 7.1):
    lamp((35, y, 4.38), .2)
for y in (-10.2, 10.2):
    cube("Second class arch", (35, y, 3.5), (5.0, .3, .4), BRASS, .08)

# Zone 3: first-class promenade/salon, wide, clean, and conspicuously luxurious.
O3 = (75, 0, 0)
room_shell("First class", O3, 13, 25, 6.1, IVORY, LIGHT_WOOD)
cube("First class carpet", (75, 0, .16), (5.2, 23.5, .1), CARPET, .02)
for y in (-8, -3, 2, 7):
    for side in (-1, 1):
        x = 75 + side * 5.8
        cube("Panoramic window", (x, y, 3.45), (.16, 3.0, 2.15), GLASS, .14)
        cube("Window brass sill", (x - side * .08, y, 2.3), (.18, 3.3, .12), BRASS, .04)
for y in (-7.2, 0, 7.2):
    cube("Salon table", (75, y, 1.25), (2.7, 1.5, .16), WOOD, .12)
    cylinder("Salon table stem", (75, y, .68), .15, 1.05, BRASS)
    for dx in (-1.9, 1.9):
        cube("Upholstered chair", (75 + dx, y, .8), (1.05, 1.0, 1.55), FABRIC, .18)
for y in (-8.5, -2.8, 2.9, 8.6):
    lamp((75, y, 5.62), .28)
for side in (-1, 1):
    cube("Decorative column", (75 + side * 5.35, 0, 3.05), (.45, .65, 5.7), BRASS, .16)

# Small navigation markers are invisible in the final render but make zones discoverable.
for name, loc in (("SPAWN_THIRD", (0, 9, 1.72)), ("SPAWN_SECOND", (35, 9.5, 1.72)), ("SPAWN_FIRST", (75, 9.5, 1.72))):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=loc)
    bpy.context.object.name = name

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "blender" / "nanan_interiors.blend"))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=str(OUT), export_format="GLB", export_apply=True, export_yup=True, export_materials="EXPORT")
