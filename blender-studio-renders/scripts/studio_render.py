"""Studio product renders (Cycles CPU) — generalized template.

Renders a full set of studio shots (hero / side / top / details / color
variants) for one product model, using a 3-point area-light rig + overhead
softbox on a seamless white sweep.

Usage:
  blender --background --python studio_render.py -- test
  blender --background --python studio_render.py -- all

  test : render SHOTS[0] once at TEST_RES so you can judge the lighting
  all  : render every shot in SHOTS at FINAL_RES into OUTPUT_DIR

Fill in the CONFIG block below for your product. Modeling is NOT included:
either point MODEL_BLEND at a .blend whose product objects are already named,
or point MODEL_SCRIPT at a bpy build script and set MODEL_CUT_MARKER to the
comment line where that script starts doing its own lighting (everything
before the marker is executed to rebuild the model; its lights are skipped
so this template's studio rig is the only one).
"""
import bpy, math, os, sys
from mathutils import Vector

# ================= CONFIG =================
CONFIG = {
    # --- model source: set ONE of these ---
    "MODEL_BLEND": "",            # e.g. "~/models/my_product.blend"
    "MODEL_SCRIPT": "",           # e.g. "~/models/build_my_product.py"
    "MODEL_CUT_MARKER": "# ---------------- lights ----------------",

    # --- output ---
    "OUTPUT_DIR": "~/studio_renders/output",
    "FINAL_RES": 1200,            # square finals
    "TEST_RES": 800,              # cheap lighting test

    # --- product rigging ---
    # Objects (by name) that make up the product; they get parented under one
    # PRODUCT root empty so the whole product can be lifted onto the ground.
    "PRODUCT_OBJECTS": ["GEO_body", "GEO_top", "GEO_bottom", "GEO_detail"],
    "ROOT_LIFT_Z": 1.0,           # raise root so the product rests on z = 0
    "PRODUCT_CENTER": (0, 0, 8),  # visual center: lights aim here

    # --- render ---
    "SAMPLES": 48,                # 40-48 + OpenImageDenoise is enough for stills
}

# Color variants: material name -> linear RGB. "base" is the full set; other
# variants only override what changes and inherit the rest (see VARIANTS).
BASE_MATS = {
    "MAT_body": (0.020, 0.020, 0.022),
    "MAT_grip": (0.015, 0.015, 0.018),
    "MAT_shaft": (0.030, 0.030, 0.032),
    "MAT_knob": (0.025, 0.025, 0.028),
    "MAT_seam": (0.010, 0.010, 0.012),
}
VARIANTS = {
    "base": BASE_MATS,
    "red": {
        "MAT_body": (0.380, 0.025, 0.030),
        "MAT_grip": (0.300, 0.020, 0.025),
        **{k: v for k, v in BASE_MATS.items() if k not in ("MAT_body", "MAT_grip")},
    },
    # add one dict per colorway...
}

# Shot list: (name, variant, cam_loc, cam_target, lens_mm, part_offsets, fstop)
#   part_offsets: {object_name: (x, y, z)} applied for this shot only
#                 (e.g. slide a mechanism part out for an "in-use" pose);
#                 offsets are reset before every shot.
#   fstop: 0 = depth of field off (heroes); 2.8-5.6 = DOF focused on cam_target
#                 (detail/macro shots only).
SHOTS = [
    ("hero_34",        "base", (19, -23, 14),   (0.5, 0, 7.5),   50, {}, 0),
    ("side",           "base", (3, -30, 9),     (0, 0, 8),       50, {}, 0),
    ("top",            "base", (0.5, -1, 36),   (0.5, 0, 4),     50, {}, 0),
    ("detail_mech",    "base", (16, -9, 13),    (6.5, 0, 10.3),  85, {"GEO_detail": (1.5, 0, 0)}, 4.0),
    ("detail_badge",   "base", (11, -13, 10.5), (2, -2.3, 8.6),  85, {}, 4.0),
    ("in_use",         "base", (21, -25, 13),   (0, 0, 7.5),     50, {"GEO_detail": (1.5, 0, 0)}, 0),
    ("hero_34_red",    "red",  (19, -23, 14),   (0.5, 0, 7.5),   50, {}, 0),
    # one hero_34 per extra colorway...
]

# ================= helpers =================
def aim(obj, target):
    """Point an object (camera or light) at a world-space target."""
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

# ================= load model =================
if CONFIG["MODEL_BLEND"]:
    bpy.ops.wm.open_mainfile(filepath=os.path.expanduser(CONFIG["MODEL_BLEND"]))
elif CONFIG["MODEL_SCRIPT"]:
    path = os.path.expanduser(CONFIG["MODEL_SCRIPT"])
    src = open(path, encoding="utf-8").read()
    model_src = src.split(CONFIG["MODEL_CUT_MARKER"])[0]
    ns = {"bpy": bpy, "math": math, "os": os, "Vector": Vector}
    exec(compile(model_src, path, "exec"), ns)
else:
    raise SystemExit("CONFIG: set MODEL_BLEND or MODEL_SCRIPT")

OUT = os.path.expanduser(CONFIG["OUTPUT_DIR"])
os.makedirs(OUT, exist_ok=True)

# ================= rig product under one root =================
root = bpy.data.objects.new("PRODUCT", None)
bpy.context.collection.objects.link(root)
_base_loc = {}
for name in CONFIG["PRODUCT_OBJECTS"]:
    ob = bpy.data.objects[name]
    _base_loc[name] = tuple(ob.location)
    ob.parent = root
root.location.z = CONFIG["ROOT_LIFT_Z"]

# ================= stage: white sweep + ground =================
def make_mat_simple(name, base, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = 0.0
    return m

bpy.ops.mesh.primitive_plane_add(size=440, location=(0, 0, 0))
ground = bpy.context.view_layer.objects.active
ground.name = "studio_ground"
ground.data.materials.append(make_mat_simple("MAT_ground", (0.97, 0.97, 0.96), 0.9))
# Cycles shadows on the ground give the contact shadow that grounds the product.
# For transparent-background compositing instead, enable instead:
#   ground.is_shadow_catcher = True  (and scn.render.film_transparent = True)

world = bpy.context.scene.world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
bg.inputs["Strength"].default_value = 1.6

# ================= lights: 3-point + top softbox =================
def area_light(name, loc, energy, size, target):
    bpy.ops.object.light_add(type='AREA', location=loc)
    l = bpy.context.view_layer.objects.active
    l.name = name
    l.data.energy = energy
    l.data.size = size
    aim(l, target)
    return l

C = CONFIG["PRODUCT_CENTER"]
area_light("Key",  (15, -13, 21), 1600, 5.0,  C)   # main: harder, directional
area_light("Fill", (-15, 11, 13),  150, 9.0,  C)   # fill: ~10x weaker than key
area_light("Rim",  (-7, 15, 19),  1500, 7.0,  C)   # rim: edge separation
area_light("Top",  (0, 2, 32),     200, 12.0, C)   # overhead softbox, minimal

# ================= camera =================
bpy.ops.object.camera_add(location=(19, -23, 14))
cam = bpy.context.view_layer.objects.active
cam.name = "StudioCam"
bpy.context.scene.camera = cam

def shoot(loc, tgt, lens, fstop):
    cam.location = loc
    cam.data.lens = lens
    aim(cam, tgt)
    if fstop and fstop > 0:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = (Vector(tgt) - Vector(loc)).length
        cam.data.dof.aperture_fstop = fstop
    else:
        cam.data.dof.use_dof = False

# ================= variants =================
def set_variant(mats):
    for mat_name, rgb in mats.items():
        m = bpy.data.materials[mat_name]
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1.0)

# ================= render config =================
# Headless / GPU-less machines: Eevee needs an EGL context and will crash or
# fail on VMs without a GPU stack. Cycles on CPU is the reliable path.
scn = bpy.context.scene
scn.render.engine = 'CYCLES'
scn.cycles.device = 'CPU'
scn.cycles.samples = CONFIG["SAMPLES"]
scn.cycles.use_denoising = True
try:
    scn.cycles.denoiser = 'OPENIMAGEDENOISE'
except TypeError:
    pass
scn.view_settings.view_transform = 'Standard'   # keeps the white sweep + colors honest
scn.view_settings.exposure = 0.1
scn.render.film_transparent = False
scn.render.image_settings.file_format = 'PNG'

# ================= shoot =================
def render_shot(name, variant, loc, tgt, lens, offsets, fstop, res):
    set_variant(VARIANTS[variant])
    for obj_name, base in _base_loc.items():
        bpy.data.objects[obj_name].location = base
    for obj_name, off in offsets.items():
        ob = bpy.data.objects[obj_name]
        ob.location = tuple(b + o for b, o in zip(_base_loc[obj_name], off))
    shoot(loc, tgt, lens, fstop)
    scn.render.resolution_x = res
    scn.render.resolution_y = res
    scn.render.resolution_percentage = 100
    scn.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("STUDIO_DONE", scn.render.filepath)

mode = "test"
if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1:]
    if args:
        mode = args[0]

if mode == "test":
    n, v, loc, tgt, lens, off, fs = SHOTS[0]
    render_shot("studio_test_lighting", v, loc, tgt, lens, off, fs, CONFIG["TEST_RES"])
else:
    for s in SHOTS:
        render_shot(*s, CONFIG["FINAL_RES"])
print("STUDIO_ALL_DONE", mode)
