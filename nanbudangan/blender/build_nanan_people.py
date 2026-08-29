"""Build the reusable cast and first-person arms for the Nan'an harbour scene.

The underlying human topology is the CC0 `male_3d.blend` by Drummyfish.
All period clothing, poses and scene-ready variants are authored here.
"""
import bpy
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "source" / "male_3d.blend"
MODEL_DIR = ROOT / "static" / "nanbudangan" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def mat(name, color, rough=.68, metallic=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metallic
    return m


SKIN = NAVY = KHAKI = CREAM = BLACK = BRASS = None


def init_mats():
    global SKIN, NAVY, KHAKI, CREAM, BLACK, BRASS
    SKIN = mat("warm south-seas skin", (.37, .20, .13), .72)
    NAVY = mat("sailor navy", (.035, .065, .075), .64)
    KHAKI = mat("traveller khaki", (.22, .25, .18), .82)
    CREAM = mat("shirt cotton", (.62, .59, .48), .9)
    BLACK = mat("hair and shoe", (.018, .014, .012), .6)
    BRASS = mat("uniform brass", (.48, .30, .08), .32, .55)


def cube(name, location, scale, material, bevel=.025, parent=None, bone=None):
    bpy.ops.mesh.primitive_cube_add(location=location)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(material)
    if bevel:
        mod = ob.modifiers.new("soft tailoring", "BEVEL")
        mod.width, mod.segments = bevel, 2
    # Costume panels remain in armature-object space. The harbour cast only
    # uses subtle upper-body animation, avoiding bone-parent offset drift in glTF.
    if parent:
        ob.location += parent.location
    return ob


def uv(name, location, scale, material, parent=None, bone=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=location)
    ob = bpy.context.object
    ob.name, ob.scale = name, scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(material)
    if parent:
        ob.location += parent.location
    return ob


def cylinder(name, location, radius, depth, material, parent=None, bone=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=radius, depth=depth, location=location)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(material)
    if parent:
        ob.location += parent.location
    return ob


def clear_action(arm):
    arm.animation_data_clear()
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)


def add_idle_and_wave(arm):
    clear_action(arm)
    arm.animation_data_create()
    action = bpy.data.actions.new("Sailor_Idle")
    arm.animation_data.action = action
    for frame in (1, 48):
        for bone, angles in {
            "arm_upper.L": (0, .08, 1.08), "arm_lower.L": (0, 0, .10),
            "arm_upper.R": (0, -.08, -1.08), "arm_lower.R": (0, 0, -.10),
        }.items():
            pb = arm.pose.bones[bone]
            pb.rotation_euler = angles
            pb.keyframe_insert("rotation_euler", frame=frame)
    # A courteous nod in the middle of the idle cycle.
    head = arm.pose.bones["head"]
    for frame, angle in ((1, 0), (22, .13), (34, 0), (48, 0)):
        head.rotation_euler.x = angle
        head.keyframe_insert("rotation_euler", frame=frame)
    # Blender's default Bezier interpolation gives the nod a soft, human cadence.


def dress_character():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    init_mats()
    arm = bpy.data.objects["Armature"]
    body = bpy.data.objects["body"]
    body.name = "Sailor_Body"
    body.data.materials.clear()
    for material in (SKIN, NAVY, BLACK):
        body.data.materials.append(material)
    # Paint the period uniform directly onto the skinned topology. This keeps
    # the actual shoulder, waist and leg silhouette instead of building a box
    # around the body. Only face and articulated hands remain bare.
    verts = body.data.vertices
    group_names = {group.index: group.name for group in body.vertex_groups}
    for poly in body.data.polygons:
        influences = []
        for index in poly.vertices:
            influences.extend((weight.weight, group_names.get(weight.group, "")) for weight in verts[index].groups)
        dominant = max(influences, default=(0, ""))[1]
        if dominant.startswith("foot."):
            poly.material_index = 2
        elif dominant in {"head", "neck"} or dominant.startswith(("palm.", "finger_")):
            poly.material_index = 0
        else:
            poly.material_index = 1
    cube("Sailor_Collar_L", (-.08, -.115, .55), (.065, .018, .085), CREAM, .014, arm)
    cube("Sailor_Collar_R", (.08, -.115, .55), (.065, .018, .085), CREAM, .014, arm)
    cube("Sailor_Belt", (0, -.005, .11), (.245, .145, .022), BLACK, .012, arm)
    for side, suffix in ((-1, "R"), (1, "L")):
        # Brass shoulder tab adds a readable period-uniform silhouette.
        cube(f"Epaulette_{suffix}", (side*.22, .035, .59), (.10, .13, .018), BRASS, .014, arm)
    cylinder("Sailor_Cap", (0, .015, .83), .16, .07, CREAM, arm, "head")
    cylinder("Sailor_CapBand", (0, .015, .79), .155, .055, NAVY, arm, "head")
    uv("Hair", (0, .055, .76), (.145, .13, .12), BLACK, arm, "head")
    add_idle_and_wave(arm)
    bpy.context.scene.render.fps = 24
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 48
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "blender" / "nanan_people.blend"))
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(MODEL_DIR / "nanan_people.glb"), export_format="GLB",
        export_apply=True, export_yup=True, export_animations=True,
    )


def make_first_person_arms():
    # Start again so the view model contains no loose costume geometry.
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    init_mats()
    arm, body = bpy.data.objects["Armature"], bpy.data.objects["body"]
    body.data.materials.clear(); body.data.materials.append(SKIN)
    keep_prefixes = ("collar.", "arm_upper.", "arm_lower.", "palm.", "finger_")
    keep_groups = {g.index for g in body.vertex_groups if g.name.startswith(keep_prefixes)}
    mesh = body.data
    remove = [v.index for v in mesh.vertices if not any(g.group in keep_groups and g.weight > .05 for g in v.groups)]
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for idx in remove: mesh.vertices[idx].select = True
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.delete(type="VERT"); bpy.ops.object.mode_set(mode="OBJECT")
    body.name = "Zhang_Haiyan_FirstPerson_Arms"
    # Military cuffs follow the forearm bones, leaving the real articulated hands visible.
    for side, suffix in ((-1, "R"), (1, "L")):
        cube(f"Military_Sleeve_{suffix}", (side*.48, .015, .405), (.28, .15, .13), KHAKI, .04, arm, f"arm_lower.{suffix}")
        cube(f"Cuff_{suffix}", (side*.625, -.005, .35), (.07, .13, .10), NAVY, .025, arm, f"palm.{suffix}")
    clear_action(arm)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(MODEL_DIR / "nanan_first_person_arms.glb"), export_format="GLB",
        export_apply=True, export_yup=True, export_animations=False,
    )


dress_character()
make_first_person_arms()
