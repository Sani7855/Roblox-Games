"""
Meadowvale stylized barns — standalone Expanded Red Plank Barn generator

Builds only progression Level 1 (Expanded Red Plank Barn) and places one expanded barn per farm.
Barn scale is 0.90, slightly larger than the previous 0.82 version, and placement
uses the pathway-aligned center position, shifted slightly left. Requires Meadowvale_Block_Farms.blend
to be available beside the current project/script or at the configured fallback path.
Save the scene with Ctrl+S after checking it in Blender.
"""
import bpy, bmesh, os, re, math, traceback
from mathutils import Matrix, Vector

# ---------------- settings ----------------
LEVELS = (1,)
SCALE = 0.90
SPACING = 30.5  # unused for this single-barn version
LEAN_DEG = {1: 0.0, 2: 1.2, 3: -1.2}
BARN_Z = 0.35
BARN_SHIFT_X = -2.0  # nudge the single expanded barn slightly left toward pathway centerline
ENTRANCE_HALF_WIDTH = 9.0  # wider than the previous 8-unit half opening
DOOR_OPEN_DEG = 70.0       # doors swing outward from the entrance
SIDE_ENTRY_CENTER_Y = 17.4
SIDE_ENTRY_HALF_WIDTH = 3.8
SIDE_ENTRY_HEIGHT = 7.2
SRC_NAME = "Meadowvale_Block_Farms.blend"
FALLBACK = r"C:\Users\Manoj\OneDrive\Desktop\Meadowvale_Block_Farms.blend"
LIB_NAME = "Barn_Library_Source"
ZB = 2.0                       # top of the ground floor slab (inside the barn)
# Shared dimensions for the third-barn ladder hatch. Kept close to the left wall but
# with enough clearance for the rails and a character to climb through comfortably.
LADDER_HOLE_X0 = -24.0
LADDER_HOLE_X1 = -19.0
LADDER_HOLE_Y0 = 6.5
LADDER_HOLE_Y1 = 13.5
LADDER_CENTRE_X = (LADDER_HOLE_X0 + LADDER_HOLE_X1) / 2.0
LADDER_CENTRE_Y = (LADDER_HOLE_Y0 + LADDER_HOLE_Y1) / 2.0

# Classic but slightly eerie barn reds. Trim stays dark, warm timber rather than neon.
ACCENT = {1: ("MossTrim1", (0.24, 0.085, 0.035)),
          2: ("RustTrim2", (0.27, 0.085, 0.035)),
          3: ("OliveTrim3", (0.22, 0.075, 0.032))}
WALL = {1: (0.56, 0.075, 0.055),   # classic barn red
        2: (0.46, 0.045, 0.038),   # deeper brick red
        3: (0.60, 0.085, 0.060)}   # rusty crimson
ROOF = {1: (0.19, 0.045, 0.035),
        2: (0.15, 0.030, 0.026),
        3: (0.20, 0.045, 0.032)}
AMP = {1: 2.0, 2: 2.4, 3: 2.6}
# roof shape per level (heights relative to the top of the walls)
ROOFP = {
    1: dict(p1x=-17.0, p1h=9.0, rx=4.0, rise=0.0, p3x=15.0, p3h=11.0, droop=2.0, wave=1.2, seed=1.3),
    2: dict(p1x=-15.0, p1h=11.0, rx=-5.0, rise=2.5, p3x=17.0, p3h=8.5, droop=1.2, wave=1.8, seed=2.1),
    3: dict(p1x=-18.0, p1h=8.0, rx=2.0, rise=4.0, p3x=14.0, p3h=12.0, droop=2.5, wave=1.5, seed=3.7),
}

REPORT = []
def log(msg):
    print("[BARNS]", msg)
    REPORT.append(msg)

def base(n):
    return re.sub(r"\.\d{3}$", "", n)

def all_objects(col):
    out = list(col.objects)
    for ch in col.children:
        out += all_objects(ch)
    return out

def find_layer_collection(lc, name):
    if lc.name == name:
        return lc
    for ch in lc.children:
        r = find_layer_collection(ch, name)
        if r:
            return r
    return None

def remove_collection_tree(col):
    for ch in list(col.children):
        remove_collection_tree(ch)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(col)

# ---------------- 1. import ----------------
def find_src():
    cands = []
    if bpy.data.filepath:
        cands.append(os.path.join(os.path.dirname(bpy.data.filepath), SRC_NAME))
    cands.append(os.path.join(os.path.expanduser("~"), "Desktop", SRC_NAME))
    cands.append(FALLBACK)
    for c in cands:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("Could not find " + SRC_NAME)

def principled(m):
    if m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                return n
    return None

def mat_sig(m):
    n = principled(m)
    if not n:
        return None
    return list(n.inputs["Base Color"].default_value)[:3] + [n.inputs["Emission Strength"].default_value]

def import_barns():
    missing = [n for n in LEVELS if "Barn_Level_%d" % n not in bpy.data.collections]
    if missing:
        src = find_src()
        log("Importing from " + src)
        before = set(m.name for m in bpy.data.materials)
        wanted = ["Barn_Level_%d" % n for n in missing]
        with bpy.data.libraries.load(src, link=False) as (df, dt):
            found = [w for w in wanted if w in df.collections]
            if len(found) != len(wanted):
                raise RuntimeError("Source file is missing: %s" % [w for w in wanted if w not in found])
            dt.collections = list(found)
        for m in list(bpy.data.materials):
            if m.name in before:
                continue
            b = base(m.name)
            o = bpy.data.materials.get(b) if b != m.name else None
            if o and o.name in before:
                s1, s2 = mat_sig(o), mat_sig(m)
                if s1 and s2 and all(abs(a - c) < 0.02 for a, c in zip(s1, s2)):
                    m.user_remap(o)
                    bpy.data.materials.remove(m)
    scene = bpy.context.scene
    lib = bpy.data.collections.get(LIB_NAME) or bpy.data.collections.new(LIB_NAME)
    if lib.name not in scene.collection.children:
        scene.collection.children.link(lib)
    for n in LEVELS:
        c = bpy.data.collections["Barn_Level_%d" % n]
        if c.name not in lib.children:
            lib.children.link(c)
    lc = find_layer_collection(bpy.context.view_layer.layer_collection, lib.name)
    if lc:
        lc.exclude = True
    return lib

# ---------------- 2. materials and mesh helpers ----------------
MATS = {}
DEFAULTS = {
    "CliffLight": (0.48, 0.37, 0.24), "Cliff": (0.29, 0.20, 0.11), "Hay": (0.66, 0.46, 0.15),
    "WindowGlass": (0.18, 0.42, 0.45), "GlassHighlight": (0.48, 0.68, 0.65), "Door": (0.31, 0.14, 0.055),
    "WoodHighlight": (0.72, 0.48, 0.22),
    "PlankRedLight": (0.64, 0.105, 0.075),
    "PlankRedDark": (0.43, 0.045, 0.038),
    "DisplayGreen": (0.075, 0.40, 0.085),
    "DisplayWalkway": (0.34, 0.20, 0.105),
    "FloorWoodLight": (0.43, 0.235, 0.12),
    "FloorWoodDark": (0.30, 0.145, 0.075)
}

def new_mat(name, color, emit=0.0, rough=0.7, metal=0.0):
    # Update existing materials too, so rerunning this script recolours the scene.
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    p = principled(m)
    if p:
        p.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
        p.inputs["Roughness"].default_value = rough
        p.inputs["Metallic"].default_value = metal
        emission_color = p.inputs.get("Emission Color")
        if emission_color is None:
            emission_color = p.inputs.get("Emission")
        if emission_color is not None:
            emission_color.default_value = (color[0], color[1], color[2], 1.0)
        emission_strength = p.inputs.get("Emission Strength")
        if emission_strength is not None:
            emission_strength.default_value = emit
    m.diffuse_color = (color[0], color[1], color[2], 1.0)
    return m

def getmat(key):
    m = MATS.get(key)
    if m:
        return m
    m = new_mat("Barn extra | " + key, DEFAULTS.get(key, (0.5, 0.5, 0.5)))
    MATS[key] = m
    return m

def setup_materials():
    for n in LEVELS:
        key, col = ACCENT[n]
        MATS[key] = new_mat("Barn Trim " + str(n), col, emit=0.0, rough=0.78)
        MATS["Wall%d" % n] = new_mat("Mutant Wall L%d" % n, WALL[n], rough=0.82)
        MATS["Roof%d" % n] = new_mat("Mutant Roof L%d" % n, ROOF[n], rough=0.78)
    MATS["MutGlow"] = new_mat("Mutant Window Glow", (0.62, 0.31, 0.075), emit=0.12, rough=0.52)
    MATS["WindowGlass"] = new_mat("Barn blue-green glass", (0.18, 0.42, 0.45), emit=0.10, rough=0.24)
    MATS["GlassHighlight"] = new_mat("Barn glass reflection", (0.48, 0.68, 0.65), emit=0.04, rough=0.22)
    MATS["Door"] = new_mat("Barn dark timber door", (0.31, 0.14, 0.055), rough=0.82)
    MATS["WoodHighlight"] = new_mat("Barn weathered timber highlight", (0.72, 0.48, 0.22), rough=0.8)
    MATS["PlankRedLight"] = new_mat("Barn red plank | sun-worn", (0.64, 0.105, 0.075), rough=0.88)
    MATS["PlankRedDark"] = new_mat("Barn red plank | shadow", (0.43, 0.045, 0.038), rough=0.9)
    MATS["DisplayGreen"] = new_mat("Plain green display pads", (0.075, 0.40, 0.085), rough=0.86)
    MATS["DisplayWalkway"] = new_mat("Display access walkway | warm timber", (0.34, 0.20, 0.105), rough=0.84)
    MATS["FloorWoodLight"] = new_mat("Barn floor plank | warm oak", (0.43, 0.235, 0.12), rough=0.88)
    MATS["FloorWoodDark"] = new_mat("Barn floor plank | shaded oak", (0.30, 0.145, 0.075), rough=0.9)
    MATS["Bone"] = new_mat("Mutant Bone", (0.75, 0.66, 0.44), rough=0.65)
    MATS["Tongue"] = new_mat("Mutant Tongue", (0.55, 0.16, 0.12), rough=0.7)
    MATS["Sneaker"] = new_mat("Mutant Sneaker", (0.64, 0.48, 0.28), rough=0.75)
    MATS["Sock"] = new_mat("Mutant Sock", (0.37, 0.27, 0.16), rough=0.9)
    MATS["Horn"] = new_mat("Mutant Horn", (0.70, 0.54, 0.30), rough=0.7)
    MATS["CowSpot"] = new_mat("Mutant Cow Spot", (0.10, 0.055, 0.03), rough=0.85)
    MATS["Pink"] = new_mat("Mutant Flesh", (0.52, 0.25, 0.19), rough=0.7)
    MATS["Tentacle"] = new_mat("Mutant Tentacle", (0.27, 0.32, 0.12), rough=0.65)
    MATS["Tumor"] = new_mat("Mutant Tumor", (0.45, 0.20, 0.14), rough=0.75)
    MATS["Pustule"] = new_mat("Mutant Pustule", (0.62, 0.54, 0.12), emit=0.18, rough=0.75)

def smooth(me):
    try:
        me.shade_smooth()
    except Exception:
        for p in me.polygons:
            p.use_smooth = True

def cube_mesh(key):
    name = "Barn Extra Cube | " + key
    me = bpy.data.meshes.get(name)
    if me:
        return me
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(getmat(key))
    return me

def sphere_mesh(name, r, key, seg=24, rings=12):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    bm.to_mesh(me)
    bm.free()
    smooth(me)
    me.materials.append(getmat(key))
    return me

UNIT = {}
def unit_sphere(key):
    k = "S" + key
    if k not in UNIT:
        UNIT[k] = sphere_mesh("Barn Unit Sphere | " + key, 1.0, key, 20, 10)
    return UNIT[k]

def torus_mesh(name, R, r, key, seg=40, ring=8):
    verts, faces = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for j in range(ring):
            b = 2 * math.pi * j / ring
            rr = R + r * math.cos(b)
            verts.append((rr * math.cos(a), rr * math.sin(a), r * math.sin(b)))
    for i in range(seg):
        for j in range(ring):
            a = i * ring + j
            b = ((i + 1) % seg) * ring + j
            c = ((i + 1) % seg) * ring + (j + 1) % ring
            d = i * ring + (j + 1) % ring
            faces.append((a, b, c, d))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    smooth(me)
    me.materials.append(getmat(key))
    return me

def unit_ring(key):
    k = "R" + key
    if k not in UNIT:
        UNIT[k] = torus_mesh("Barn Unit Ring | " + key, 1.0, 0.07, key)
    return UNIT[k]

def frustum_mesh(name, r_bottom, r_top, depth, key, seg=24, caps=False, phase=0.0):
    verts, faces = [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg + phase
        verts.append((r_bottom * math.cos(a), r_bottom * math.sin(a), -depth / 2.0))
    for k in range(seg):
        a = 2 * math.pi * k / seg + phase
        verts.append((r_top * math.cos(a), r_top * math.sin(a), depth / 2.0))
    for k in range(seg):
        faces.append((k, (k + 1) % seg, seg + (k + 1) % seg, seg + k))
    if caps:
        faces.append(tuple(reversed(range(seg))))
        faces.append(tuple(range(seg, 2 * seg)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    smooth(me)
    me.materials.append(getmat(key))
    return me

def tube_mesh(name, pts, radii, key, seg=10):
    verts, faces = [], []
    n = len(pts)
    prev = None
    for i in range(n):
        p = Vector(pts[i])
        t = (Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        if prev is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            nr = t.cross(ref).normalized()
        else:
            nr = (prev - t * prev.dot(t)).normalized()
        bn = t.cross(nr)
        prev = nr
        for k in range(seg):
            a = 2 * math.pi * k / seg
            v = p + (nr * math.cos(a) + bn * math.sin(a)) * radii[i]
            verts.append(tuple(v))
    for i in range(n - 1):
        for k in range(seg):
            a = i * seg + k
            b = i * seg + (k + 1) % seg
            c = (i + 1) * seg + (k + 1) % seg
            d = (i + 1) * seg + k
            faces.append((a, b, c, d))
    ci = len(verts)
    verts.append(tuple(pts[-1]))
    for k in range(seg):
        faces.append((ci, (n - 1) * seg + k, (n - 1) * seg + (k + 1) % seg))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    smooth(me)
    me.materials.append(getmat(key))
    return me

def param_surface(name, nu, nv, pos_fn, skip_fn, key):
    verts = []
    for i in range(nu + 1):
        for j in range(nv + 1):
            verts.append(tuple(pos_fn(i / nu, j / nv)))
    faces = []
    for i in range(nu):
        for j in range(nv):
            if skip_fn and skip_fn((i + 0.5) / nu, (j + 0.5) / nv):
                continue
            a = i * (nv + 1) + j
            b = (i + 1) * (nv + 1) + j
            c = (i + 1) * (nv + 1) + j + 1
            d = i * (nv + 1) + j + 1
            faces.append((a, b, c, d))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    smooth(me)
    me.materials.append(getmat(key))
    return me

def attach(o, parent):
    if parent is not None:
        o.parent = parent
        o.matrix_parent_inverse = Matrix.Identity(4)

def mobj(name, col, me, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), parent=None):
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.rotation_euler = rot
    o.scale = scale
    col.objects.link(o)
    attach(o, parent)
    return o

def box(name, col, key, dims, loc, rot=(0.0, 0.0, 0.0), parent=None):
    return mobj(name, col, cube_mesh(key), loc, rot, dims, parent)

def pivot(name, col, loc, rot=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "PLAIN_AXES"
    e.empty_display_size = 1.0
    e.location = loc
    e.rotation_euler = rot
    col.objects.link(e)
    return e

def solid(o, t):
    m = o.modifiers.new("Thick", "SOLIDIFY")
    m.thickness = t
    m.offset = 0.0
    try:
        m.use_even_offset = True
    except Exception:
        pass

# ---------------- 3. mutant shell ----------------
def nz(a, b, seed):
    return 0.5 * (math.sin(a * 0.37 + seed) + math.sin(b * 0.53 + seed * 1.9) * math.cos(a * 0.21 - seed * 0.7))

def wall_w(u, v):
    su = math.sin(math.pi * min(1.0, max(0.0, u)))
    sv = math.sin(math.pi * min(1.0, max(0.0, v)))
    return (su * sv) ** 0.7

def roof_profile(x, p):
    """Clean symmetric gable profile used to position rooftop mutations."""
    return 14.0 * max(0.0, 1.0 - abs(x) / 27.0)

def roof_z(x, y, z0, p):
    return z0 + roof_profile(x, p)

def side_windows(L, seed):
    out = []
    ys = (-17.0, -6.0, 6.0, 17.0)
    for f in range(L):
        zc = ZB + 14.0 * f + 8.0
        for k, y in enumerate(ys):
            j = math.sin(seed * 3.1 + f * 1.7 + k * 2.3)
            out.append((y + 1.2 * j, zc + math.cos(seed + k * 1.9 + f),
                        2.0 + 0.7 * abs(j), 2.7 + 0.8 * math.cos(k + f + seed)))
    return out

def end_windows(L, seed):
    out = []
    xs = (-18.0, -5.5, 7.5)
    for f in range(1, L):
        zc = ZB + 14.0 * f + 8.0
        for k, x in enumerate(xs):
            j = math.sin(seed * 2.3 + f * 1.3 + k * 2.9)
            out.append((x + 1.0 * j, zc + 0.8 * math.cos(seed + k + f),
                        2.2 + 0.6 * abs(j), 2.8 + 0.7 * math.cos(k * 1.3 + f + seed)))
    return out

def make_side_wall(L, sx, p, seed, amp, key, wins):
    z0 = ZB + 14.0 * L
    def top(y):
        return roof_z(sx * 25.0, y, z0, p) - 0.3
    def pos(u, v):
        y = -24.5 + 49.0 * u
        z = ZB + v * (top(y) - ZB)
        w = wall_w(u, v)
        d = amp * w * (0.6 + 0.4 * nz(y, z, seed))
        return (sx * (25.0 + d), y + 0.5 * w * math.sin(z * 0.4 + seed), z)
    def skip(u, v):
        y = -24.5 + 49.0 * u
        z = ZB + v * (top(y) - ZB)
        for (a, b, ra, rb) in wins:
            if ((y - a) / ra) ** 2 + ((z - b) / rb) ** 2 < 1.0:
                return True
        return False
    def xat(y, z):
        u = (y + 24.5) / 49.0
        v = (z - ZB) / (top(y) - ZB)
        d = amp * wall_w(u, v) * (0.6 + 0.4 * nz(y, z, seed))
        return sx * (25.0 + d)
    me = param_surface("Mutant side wall", 49, int(14 * L + 3), pos, skip, key)
    return me, xat

def make_end_wall(L, sy, p, seed, amp, key, wins):
    z0 = ZB + 14.0 * L
    def top(x):
        return roof_z(x, 24.0, z0, p) - 0.3
    def pos(u, v):
        x = -25.5 + 51.0 * u
        z = ZB + v * (top(x) - ZB)
        w = wall_w(u, v)
        d = amp * w * (0.6 + 0.4 * nz(x, z, seed + 3.0))
        return (x + 0.5 * w * math.sin(z * 0.4 + seed), sy * (24.0 + d), z)
    def skip(u, v):
        x = -25.5 + 51.0 * u
        z = ZB + v * (top(x) - ZB)
        if -13.5 <= x <= 2.5 and z <= ZB + 10.0:
            return True
        if z > ZB + 10.0 and ((x + 5.5) / 8.0) ** 2 + ((z - (ZB + 10.0)) / 3.5) ** 2 < 1.0:
            return True
        for (a, b, ra, rb) in wins:
            if ((x - a) / ra) ** 2 + ((z - b) / rb) ** 2 < 1.0:
                return True
        return False
    def yat(x, z):
        u = (x + 25.5) / 51.0
        v = (z - ZB) / (top(x) - ZB)
        d = amp * wall_w(u, v) * (0.6 + 0.4 * nz(x, z, seed + 3.0))
        return sy * (24.0 + d)
    me = param_surface("Mutant end wall", 51, int(14 * L + 16), pos, skip, key)
    return me, yat

def build_roof(col, L, p, key, accent):
    """Two clean pitched roof slabs with low-poly trim; no lumpy or warped surfaces."""
    z0 = ZB + 14.0 * L
    pitch = math.atan2(14.0, 27.0)
    for side in (-1, 1):
        angle = -pitch if side < 0 else pitch
        cx = side * 14.0
        # The roof is deliberately built from simple box geometry for a Roblox-like silhouette.
        box("Pitched roof panel", col, key, (32.0, 54.0, 1.2),
            (cx, 0.0, z0 + 6.75), (0.0, angle, 0.0))
        # Evenly spaced restrained roof seams make it read as timber/slate, not a smooth warehouse roof.
        for yy in (-21.0, -10.5, 0.0, 10.5, 21.0):
            box("Roof plank seam", col, accent, (31.5, 0.18, 0.16),
                (cx, yy, z0 + 7.38), (0.0, angle, 0.0))
        # Heavy fascia boards at both gable ends.
        for sy in (-1, 1):
            box("Roof fascia", col, accent, (32.0, 0.75, 0.9),
                (cx, sy * 26.7, z0 + 7.38), (0.0, angle, 0.0))
    # Ridge and eaves are square timber beams, not glowing tubes.
    box("Roof ridge cap", col, accent, (1.5, 54.5, 0.9), (0.0, 0.0, z0 + 14.45))
    for side in (-1, 1):
        box("Roof eave trim", col, accent, (0.9, 54.5, 0.9), (side * 27.0, 0.0, z0 + 0.55))


def add_side_window(col, sx, y, z, accent):
    """Rectangular inset-looking window with chunky timber frame and crossbars."""
    gx, fx = sx * 25.62, sx * 25.82
    box("Rectangular window glass", col, "WindowGlass", (0.16, 3.0, 3.6), (gx, y, z))
    for yy in (y - 1.65, y + 1.65):
        box("Window frame upright", col, accent, (0.34, 0.25, 4.15), (fx, yy, z))
    for zz in (z - 1.95, z + 1.95):
        box("Window frame rail", col, accent, (0.34, 3.55, 0.25), (fx, y, zz))
    box("Window centre mullion", col, accent, (0.36, 0.15, 3.65), (fx, y, z))
    box("Window crossbar", col, accent, (0.36, 3.1, 0.15), (fx, y, z))


def add_end_window(col, sy, x, z, accent):
    gy, fy = sy * 25.12, sy * 25.32
    box("Gable rectangular window glass", col, "WindowGlass", (3.0, 0.16, 3.5), (x, gy, z))
    for xx in (x - 1.65, x + 1.65):
        box("Gable window upright", col, accent, (0.25, 0.34, 4.05), (xx, fy, z))
    for zz in (z - 1.9, z + 1.9):
        box("Gable window rail", col, accent, (3.55, 0.34, 0.25), (x, fy, zz))
    box("Gable window centre mullion", col, accent, (0.15, 0.36, 3.55), (x, fy, z))
    box("Gable window crossbar", col, accent, (3.1, 0.36, 0.15), (x, fy, z))


def add_gable_triangle(col, sy, z0, wall_key):
    y = sy * 24.5
    left = (-25.5, y, z0)
    apex = (0.0, y, z0 + 14.0)
    right = (25.5, y, z0)
    verts = [left, right, apex] if sy < 0 else [left, apex, right]
    me = bpy.data.meshes.new("Clean barn gable triangle")
    me.from_pydata(verts, [], [(0, 1, 2)])
    me.update()
    me.materials.append(getmat(wall_key))
    obj = mobj("Clean barn gable", col, me)
    solid(obj, 0.8)


def add_side_planking(col, sx, wall_base, z0, side_entry=False):
    """Long vertical red boards across the long sides, split around the side entry."""
    board_width = 1.72
    gap = 0.12
    x_face = sx * 25.66
    full_bottom = wall_base + 0.10
    full_top = z0 - 0.12
    full_h = full_top - full_bottom
    centre_z = (full_bottom + full_top) / 2.0
    index = 0
    y = -24.15
    while y <= 24.15:
        key = "PlankRedLight" if index % 3 else "PlankRedDark"
        overlaps_entry = side_entry and abs(y - SIDE_ENTRY_CENTER_Y) <= SIDE_ENTRY_HALF_WIDTH + board_width / 2.0
        if overlaps_entry:
            # Keep the opening clear but retain vertical boards above and below it.
            door_bottom = ZB + 14.0
            door_top = door_bottom + SIDE_ENTRY_HEIGHT
            lower_top = min(door_bottom - 0.12, full_top)
            upper_bottom = max(door_top + 0.12, full_bottom)
            if lower_top - full_bottom > 0.35:
                box("Vertical side red plank lower", col, key,
                    (0.18, board_width - gap, lower_top - full_bottom),
                    (x_face, y, (full_bottom + lower_top) / 2.0))
            if full_top - upper_bottom > 0.35:
                box("Vertical side red plank upper", col, key,
                    (0.18, board_width - gap, full_top - upper_bottom),
                    (x_face, y, (upper_bottom + full_top) / 2.0))
        else:
            box("Vertical side red plank", col, key,
                (0.18, board_width - gap, full_h), (x_face, y, centre_z))
        index += 1
        y += board_width


def add_end_wall_planking(col, sy, wall_base, door_top, z0):
    """Long vertical red boards on gable-end wall panels, leaving the entrance clear."""
    board_width = 1.72
    gap = 0.12
    y_face = sy * 25.02
    bottom = wall_base + 0.10
    top = z0 - 0.10
    x = -24.65
    index = 0
    while x <= 24.65:
        key = "PlankRedLight" if index % 3 else "PlankRedDark"
        intersects_door = abs(x) <= ENTRANCE_HALF_WIDTH + board_width / 2.0
        if intersects_door:
            # Only the wall panel above the door receives boards in this span.
            z_start = door_top + 0.12
            if top - z_start > 0.35:
                box("Vertical end red plank above entrance", col, key,
                    (board_width - gap, 0.18, top - z_start),
                    (x, y_face, (z_start + top) / 2.0))
        else:
            box("Vertical end red plank", col, key,
                (board_width - gap, 0.18, top - bottom),
                (x, y_face, (bottom + top) / 2.0))
        index += 1
        x += board_width


def add_gable_planking(col, sy, z0, window_on_face):
    """Tall vertical boards cut to the triangular gable profile and split around glass."""
    board_width = 1.72
    gap = 0.12
    y_face = sy * 25.02
    base_z = z0 + 0.10
    window_bottom = z0 + 4.8 - 7.6 / 2.0 - 0.18
    window_top = z0 + 4.8 + 7.6 / 2.0 + 0.18
    window_half_w = 6.0 + board_width / 2.0
    x = -24.6
    index = 0
    while x <= 24.6:
        roof_top = z0 + 14.0 * max(0.0, 1.0 - abs(x) / 25.5)
        top = roof_top - 0.15
        if top - base_z > 0.45:
            key = "PlankRedLight" if index % 3 else "PlankRedDark"
            segments = [(base_z, top)]
            if window_on_face and abs(x) <= window_half_w:
                segments = [(base_z, min(top, window_bottom)),
                            (max(base_z, window_top), top)]
            for low, high in segments:
                if high - low > 0.38:
                    box("Vertical triangular gable plank", col, key,
                        (board_width - gap, 0.16, high - low),
                        (x, y_face, (low + high) / 2.0))
        index += 1
        x += board_width


def add_display_pads(col, floor_index=0):
    """Eight compact green display pads, in two closer-spaced columns and four rows."""
    floor_z = ZB + 14.0 * floor_index
    pad_x = (-12.5, 12.5)
    pad_y = (-15.0, -4.0, 7.0, 18.0)
    for x in pad_x:
        for y in pad_y:
            box("Plain green display pad L%d" % floor_index, col, "DisplayGreen",
                (9.0, 7.2, 0.24), (x, y, floor_z + 0.14))


def add_display_walkways(col, floor_index=0):
    """Continuous plank-coloured aisle and crosswalks link every row of display pads."""
    walk_z = ZB + 14.0 * floor_index + 0.14
    walk_depth = 0.24
    prefix = "Display access L%d" % floor_index
    box(prefix + " main aisle", col, "DisplayWalkway",
        (5.0, 49.0, walk_depth), (0.0, -0.2, walk_z))
    box(prefix + " front cross-aisle", col, "DisplayWalkway",
        (49.0, 1.0, walk_depth), (0.0, -21.5, walk_z))
    for yy in (-15.0, -4.0, 7.0, 18.0):
        box(prefix + " pad crosswalk", col, "DisplayWalkway",
            (20.0, 1.2, walk_depth), (0.0, yy, walk_z))


def add_elevated_floor_planks(col, floor_index, ladder_opening=False):
    """Create timber decking; for Level 3, precisely subtract the ladder hatch from every board."""
    floor_z = ZB + 14.0 * floor_index
    board_centre_z = floor_z + 0.08
    board_depth = 0.18
    board_width = 1.78
    row_step = 1.90

    def board_rectangles_minus_hole(x0, x1, y0, y1):
        """Return non-overlapping rectangles making up a board with the hatch removed."""
        if not ladder_opening:
            return [(x0, x1, y0, y1)]
        hx0, hx1 = LADDER_HOLE_X0, LADDER_HOLE_X1
        hy0, hy1 = LADDER_HOLE_Y0, LADDER_HOLE_Y1
        ix0, ix1 = max(x0, hx0), min(x1, hx1)
        iy0, iy1 = max(y0, hy0), min(y1, hy1)
        if ix0 >= ix1 or iy0 >= iy1:
            return [(x0, x1, y0, y1)]
        pieces = [
            (x0, ix0, y0, y1),      # left of hatch
            (ix1, x1, y0, y1),      # right of hatch
            (ix0, ix1, y0, iy0),    # in front of hatch
            (ix0, ix1, iy1, y1),    # behind hatch
        ]
        return [(a, b, c, d) for a, b, c, d in pieces
                if (b - a) > 0.20 and (d - c) > 0.20]

    y = -24.0
    row = 0
    while y <= 24.01:
        # Stagger joints on alternate rows for an intentional plank-built floor.
        if row % 2 == 0:
            segments = [(-24.5, -0.12), (0.12, 24.5)]
        else:
            segments = [(-24.5, -12.45), (-12.25, 12.25), (12.45, 24.5)]
        y0, y1 = y - board_width / 2.0, y + board_width / 2.0
        for a, b in segments:
            for px0, px1, py0, py1 in board_rectangles_minus_hole(a, b, y0, y1):
                mat_key = "FloorWoodLight" if (row % 4 in (0, 1)) else "FloorWoodDark"
                label = "Top-floor timber plank" if floor_index == 2 else "First-floor timber plank"
                box(label, col, mat_key,
                    (px1 - px0, py1 - py0, board_depth),
                    ((px0 + px1) / 2.0, (py0 + py1) / 2.0, board_centre_z))
        row += 1
        y += row_step

    if ladder_opening:
        # Open hatch rim: frame pieces sit just outside the walking aperture, never across it.
        trim_z = floor_z + 0.15
        trim_depth = 0.14
        hole_w = LADDER_HOLE_X1 - LADDER_HOLE_X0
        hole_d = LADDER_HOLE_Y1 - LADDER_HOLE_Y0
        box("Top-floor ladder opening front rim", col, "Door",
            (hole_w, 0.18, trim_depth), (LADDER_CENTRE_X, LADDER_HOLE_Y0, trim_z))
        box("Top-floor ladder opening back rim", col, "Door",
            (hole_w, 0.18, trim_depth), (LADDER_CENTRE_X, LADDER_HOLE_Y1, trim_z))
        box("Top-floor ladder opening left rim", col, "Door",
            (0.18, hole_d, trim_depth), (LADDER_HOLE_X0, LADDER_CENTRE_Y, trim_z))
        box("Top-floor ladder opening right rim", col, "Door",
            (0.18, hole_d, trim_depth), (LADDER_HOLE_X1, LADDER_CENTRE_Y, trim_z))

def add_first_floor_access_path(col, n):
    """Flat pathway from the exterior stair landing into the first elevated floor.

    This deliberately does NOT descend to the ground/display floor and adds no
    interior stair or ramp. The visible timber deck underneath makes the whole
    storey walkable; these darker boards clearly mark the route from the side door.
    """
    if n not in (2, 3):
        return
    floor_z = ZB + 14.0
    path_top = floor_z + 0.19
    path_depth = 0.18
    path_centre_z = path_top - path_depth / 2.0

    # Extends through the side doorway so there is no gap between the outside
    # landing and the interior floor. It overlaps the landing and inside cross-path.
    box("First-floor doorway bridge", col, "DisplayWalkway",
        (10.4, 6.4, path_depth), (24.25, SIDE_ENTRY_CENTER_Y, path_centre_z))

    # Flat cross-path from the doorway toward the central area, then a central aisle.
    box("First-floor entrance cross-path", col, "DisplayWalkway",
        (28.0, 4.8, path_depth), (10.25, SIDE_ENTRY_CENTER_Y, path_centre_z))
    box("First-floor central walkway", col, "DisplayWalkway",
        (4.8, 40.0, path_depth), (0.0, 0.0, path_centre_z))


def add_interior_ladder(col):
    """Interior ladder from the first elevated floor to the top floor in Level 3."""
    # The barn has usable floors at ZB+14 and ZB+28; the previous version incorrectly
    # sent the ladder above the top floor instead of connecting these two levels.
    lower_z = ZB + 14.0 + 0.18
    upper_z = ZB + 28.0 + 0.85
    height = upper_z - lower_z
    centre_z = (lower_z + upper_z) / 2.0
    x = LADDER_CENTRE_X
    y = LADDER_CENTRE_Y
    rail_offset = 0.82
    for yy in (y - rail_offset, y + rail_offset):
        box("Interior ladder timber rail", col, "Door",
            (0.28, 0.30, height + 0.55), (x, yy, centre_z + 0.18))
    rung_count = 13
    for i in range(rung_count):
        t = i / max(1, rung_count - 1)
        rz = lower_z + 0.55 + t * (upper_z - lower_z - 0.70)
        box("Interior ladder rung", col, "WoodHighlight",
            (0.28, rail_offset * 2.0, 0.24), (x + 0.12, y, rz))



def add_side_entry_frame(col, n, wall_base, accent):
    """Frame an open side doorway reached by the new exterior staircase."""
    if n not in (2, 3):
        return
    x_face = 25.92
    bottom = ZB + 14.0
    top = bottom + SIDE_ENTRY_HEIGHT
    centre_y = SIDE_ENTRY_CENTER_Y
    half = SIDE_ENTRY_HALF_WIDTH
    centre_z = (bottom + top) / 2.0
    for yy in (centre_y - half, centre_y + half):
        box("Exterior stair side-entry jamb", col, accent,
            (0.50, 0.48, SIDE_ENTRY_HEIGHT), (x_face, yy, centre_z))
    box("Exterior stair side-entry header", col, accent,
        (0.50, 2.0 * half + 0.48, 0.48), (x_face, centre_y, top))


def add_exterior_staircase(col, n):
    """Build a long side-exterior stair from ground to floor one, with a landing."""
    if n not in (2, 3):
        return
    stair_x = 28.05
    tread_width = 3.05
    y_start = -22.0
    y_end = SIDE_ENTRY_CENTER_Y - 0.6
    run = y_end - y_start
    z_start = 1.0
    # The marked flat path sits 0.19 above the nominal floor datum.
    # Raise the landing to meet it; the deck boards sit only 0.02 below the path.
    z_end = ZB + 14.0 + 0.19
    rise = z_end - z_start
    count = 25
    tread_depth = run / count
    tread_rise = rise / count
    tread_thickness = 0.38

    # Each tread is a distinct chunky block, ascending along the outside long wall.
    for i in range(count):
        yy = y_start + (i + 0.5) * tread_depth
        zz = z_start + (i + 0.5) * tread_rise
        if i == count - 1:
            # Make the final tread flush with the landing's top surface.
            zz = z_end - tread_thickness / 2.0
        key = "Door" if i % 2 == 0 else "WoodHighlight"
        box("Exterior wooden stair tread", col, key,
            (tread_width, tread_depth * 0.92, tread_thickness),
            (stair_x, yy, zz))

    stair_length = math.sqrt(run * run + rise * rise)
    slope_angle = math.atan2(rise, run)
    mid_y = (y_start + y_end) / 2.0
    mid_z = (z_start + z_end) / 2.0
    # Diagonal side stringers support the entire stair flight.
    for xx in (stair_x - tread_width / 2.0 - 0.10, stair_x + tread_width / 2.0 + 0.10):
        box("Exterior stair diagonal stringer", col, "Door",
            (0.30, stair_length + 0.35, 0.42), (xx, mid_y, mid_z),
            (slope_angle, 0.0, 0.0))
        # Simple timber handrail, raised above the treads.
        box("Exterior stair wooden handrail", col, "WoodHighlight",
            (0.20, stair_length + 0.45, 0.24),
            (xx, mid_y, mid_z + 1.7), (slope_angle, 0.0, 0.0))
        for i in (0, 6, 12, 18, 24):
            yy = y_start + (i + 0.5) * tread_depth
            zz = z_start + (i + 0.5) * tread_rise + 0.85
            box("Exterior stair handrail post", col, "Door",
                (0.18, 0.20, 1.75), (xx, yy, zz))

    # A landing bridges the last tread to the open first-floor doorway.
    box("Exterior stair upper landing", col, "Door",
        (tread_width + 0.18, 4.2, 0.50),
        (stair_x, SIDE_ENTRY_CENTER_Y + 1.0, z_end - 0.25))

def add_doorway(col, sy, wall_base, door_top, accent):
    """Slightly widened centered entrance with two visibly open, hinged doors."""
    opening_half_width = ENTRANCE_HALF_WIDTH
    frame_y = sy * 25.18

    # Chunky jambs and a matching header make the wider opening easy to read.
    for xx in (-opening_half_width, opening_half_width):
        box("Entrance timber post", col, accent,
            (0.62, 0.48, door_top - wall_base + 0.5),
            (xx, frame_y, (door_top + wall_base) / 2.0))
    box("Entrance timber header", col, accent,
        (2.0 * opening_half_width + 0.7, 0.48, 0.58),
        (0.0, frame_y, door_top))

    zc = (wall_base + door_top) / 2.0
    leaf_width = opening_half_width - 0.5
    leaf_height = door_top - wall_base - 0.8
    brace_angle = math.atan2(leaf_height, leaf_width)
    open_angle = math.radians(DOOR_OPEN_DEG)

    # Each leaf is parented to a hinge at an outer edge. Opposite rotations
    # swing both leaves away from the centre and out from whichever end is viewed.
    for side in (-1, 1):
        hinge_x = side * opening_half_width
        swing = -sy * side * open_angle
        hinge = pivot(
            "Barn door hinge | %s | %s" % ("left" if side < 0 else "right",
                                           "front" if sy < 0 else "back"),
            col, (hinge_x, sy * 25.12, zc), (0.0, 0.0, swing))
        local_cx = -side * (leaf_width / 2.0)
        front_offset = sy * 0.22

        box("Open barn door leaf", col, "Door",
            (leaf_width, 0.34, leaf_height), (local_cx, 0.0, 0.0), parent=hinge)

        # Crossed timber braces and narrow boards rotate with the door leaf.
        brace_length = math.sqrt(leaf_width**2 + leaf_height**2)
        for brace_sign in (-1, 1):
            box("Open barn door diagonal brace", col, "WoodHighlight",
                (brace_length, 0.20, 0.22),
                (local_cx, front_offset, 0.0),
                (0.0, brace_sign * brace_angle, 0.0), parent=hinge)
        for offset in (-leaf_width * 0.23, leaf_width * 0.23):
            box("Open barn door board", col, accent,
                (0.16, 0.38, leaf_height - 0.4),
                (local_cx + offset, front_offset, 0.0), parent=hinge)


def add_wooden_stick_bracing(col, n, sy, wall_base, z0):
    """Add chunky timber sticks to the tall side panels of Levels 2 and 3.

    The braces are kept outside the centred doorway/window zone and follow the
    barn's storey heights, so they read like simple Roblox farmhouse framing.
    """
    face_y = sy * 25.43
    inner_x = 9.0
    outer_x = 24.0

    for side in (-1, 1):
        # One long upright on each wing, plus rails at the visible floor breaks.
        box("Rustic timber upright", col, "Door",
            (0.46, 0.44, z0 - wall_base - 0.8),
            (side * 16.5, face_y, (wall_base + z0) / 2.0))

        for floor_i in range(1, n):
            rail_z = ZB + 14.0 * floor_i
            box("Rustic timber story rail", col, "WoodHighlight",
                (15.3, 0.42, 0.42), (side * 16.5, face_y + sy * 0.035, rail_z))

        # X-braces in each storey create visible wooden-stick detail without
        # crowding the doors or adding more windows.
        for floor_i in range(n):
            z_low = wall_base + 0.75 + 14.0 * floor_i
            z_high = min(z0 - 0.75, z_low + 13.0)
            if z_high <= z_low:
                continue
            endpoints = (
                ((side * inner_x, z_low), (side * outer_x, z_high)),
                ((side * inner_x, z_high), (side * outer_x, z_low)),
            )
            for brace_index, (p1, p2) in enumerate(endpoints):
                x1, z1 = p1
                x2, z2 = p2
                dx = x2 - x1
                dz = z2 - z1
                length = math.hypot(dx, dz)
                angle = -math.atan2(dz, dx)
                key = "WoodHighlight" if brace_index == 0 else "Door"
                box("Rustic diagonal wooden stick", col, key,
                    (length, 0.38, 0.42),
                    ((x1 + x2) / 2.0, face_y + sy * 0.07, (z1 + z2) / 2.0),
                    (0.0, angle, 0.0))


def add_gable_window(col, sy, z0, accent, level=1):
    """Large centered front window; Levels 2/3 sit in the middle wall, not the gable peak."""
    x = 0.0
    z = (z0 - 6.5) if level in (2, 3) else (z0 + 4.0)
    width = 14.0
    height = 9.0
    y_glass = sy * 25.13
    y_frame = sy * 25.38

    # One continuous pane behind the timber, not a grid of little windows.
    box("Single centered gable glass pane", col, "WindowGlass",
        (width, 0.18, height), (x, y_glass, z))
    box("Gable glass reflection", col, "GlassHighlight",
        (0.48, 0.08, height - 1.2), (x - 3.35, sy * 25.245, z + 0.05))

    # Thick wooden outside frame.
    frame_w = 0.42
    frame_d = 0.38
    for xx in (-width / 2.0 - frame_w / 2.0, width / 2.0 + frame_w / 2.0):
        box("Gable window wooden upright", col, accent,
            (frame_w, frame_d, height + 0.62), (xx, y_frame, z))
    for zz in (z - height / 2.0 - frame_w / 2.0, z + height / 2.0 + frame_w / 2.0):
        box("Gable window wooden rail", col, accent,
            (width + 0.78, frame_d, frame_w), (x, y_frame, zz))

    # Narrow central divider and two X-braced glass sections.
    box("Gable window center timber", col, "Door",
        (0.32, frame_d, height), (x, y_frame - sy * 0.025, z))
    half_width = width / 2.0 - 0.65
    half_height = height / 2.0 - 0.48
    bar_length = math.hypot(half_width, half_height)
    angle = math.atan2(half_height, half_width)
    for side in (-1, 1):
        xc = side * width / 4.0
        for sign in (-1, 1):
            box("Gable window X timber brace", col, "Door",
                (bar_length, frame_d, 0.24), (xc, y_frame - sy * 0.055, z),
                (0.0, sign * angle, 0.0))


def add_fangs(col, L, yat):
    for k in range(7):
        x = -12.8 + k * 2.3
        zt = ZB + 10.0 + 3.5 * math.sqrt(max(0.0, 1.0 - ((x + 5.5) / 8.0) ** 2))
        length = 2.4 + 0.7 * math.sin(k * 1.9 + L)
        mobj("Mouth fang", col, frustum_mesh("Mouth fang", 0.03, 0.7, length, "Bone", seg=10),
             loc=(x, yat(x, zt), zt - length / 2.0 + 0.4))

def add_tongue(col, sy):
    mobj("Tongue ramp", col, cube_mesh("Tongue"), loc=(-5.5, sy * 27.75, 0.71),
         rot=(-sy * 0.298, 0.0, 0.0), scale=(11.5, 6.9, 0.6))
    mobj("Tongue tip", col, sphere_mesh("Tongue tip", 1.0, "Tongue"), loc=(-5.5, sy * 31.0, 0.5),
         scale=(5.8, 2.6, 0.9))

def add_windows(col, wins, mode, sx_or_sy, accent, getpos, count_offset=0):
    for idx, (a, b, ra, rb) in enumerate(wins):
        key = "MutGlow" if (idx + count_offset) % 2 == 0 else accent
        if mode == "side":
            sx = sx_or_sy
            x = getpos(a, b)
            mobj("Mutant window glow", col, unit_sphere(key), loc=(x, a, b), scale=(0.25, ra * 0.95, rb * 0.95))
            mobj("Mutant window ring", col, unit_ring(accent), loc=(x + sx * 0.55, a, b),
                 rot=(0, math.pi / 2.0, 0), scale=(rb, ra, 1.0))
        else:
            sy = sx_or_sy
            y = getpos(a, b)
            mobj("Mutant window glow", col, unit_sphere(key), loc=(a, y, b), scale=(ra * 0.95, 0.25, rb * 0.95))
            mobj("Mutant window ring", col, unit_ring(accent), loc=(a, y + sy * 0.55, b),
                 rot=(math.pi / 2.0, 0, 0), scale=(ra, rb, 1.0))

# ---------------- 4. per-level mutations ----------------
def level1_extras(col, p, z0):
    # The large sneaker props previously placed around the first barn entrance have
    # been intentionally removed so the entrance stays clear. Keep the small roof barn.
    # baby barn growing out of the roof
    bx, by = -14.0, 4.0
    bz = roof_z(bx, by, z0, p)
    pv = pivot("Baby barn pivot", col, (bx, by, bz - 0.5), (0.14, -0.30, 0.45))
    box("Baby barn body", col, "Wall1", (9.0, 10.0, 7.0), (0, 0, 3.0), parent=pv)
    mobj("Baby barn roof", col, frustum_mesh("Baby roof", 5.2, 5.2, 11.0, "Roof1", seg=3, caps=True, phase=math.pi / 2.0),
         loc=(0, 0, 6.6), rot=(math.pi / 2.0, 0, 0), parent=pv)
    box("Baby barn door", col, "MutGlow", (2.4, 0.4, 3.4), (0, -5.1, 1.9), parent=pv)

def level2_extras(col, p, z0, side_x):
    # Cow-inspired horns and ears. The barn walls themselves stay clean and plank-built.
    for sgn in (-1, 1):
        x0 = sgn * 15.5
        y0 = -16.0
        z = roof_z(x0, y0, z0, p) - 0.5
        pts, rad = [], []
        for i in range(14):
            t = i / 13.0
            pts.append((x0 + sgn * 9.0 * t ** 1.6, y0, z + 15.0 * t - 5.0 * t * t))
            rad.append(1.8 * (1.0 - t) + 0.12)
        mobj("Cow horn", col, tube_mesh("Cow horn", pts, rad, "Horn", seg=8))
        box("Blocky cow ear", col, "Pink", (2.4, 5.0, 2.6), (sgn * 27.6, -19.0, z0 - 2.0), (0, sgn * 0.32, 0))
    # Udder and tail stay as the brainrot signature, coloured with muted dusty rose/brown.
    mobj("Udder", col, unit_sphere("Pink"), loc=(15.0, 27.5, 5.0), scale=(5.5, 3.6, 4.0))
    for (tx, ty) in ((12.8, 26.2), (17.2, 26.2), (12.8, 28.8), (17.2, 28.8)):
        mobj("Teat", col, frustum_mesh("Teat", 0.3, 0.7, 2.4, "Pink", seg=8), loc=(tx, ty, 1.9))
    pts, rad = [], []
    for i in range(16):
        t = i / 15.0
        pts.append((-21.0, 24.3 + 8.0 * t, 11.0 - 9.0 * t + 12.0 * t * t))
        rad.append(0.95 * (1.0 - t) + 0.35)
    mobj("Cow tail", col, tube_mesh("Cow tail", pts, rad, "Wall2", seg=8))
    tip = pts[-1]
    mobj("Cow tail tuft", col, unit_sphere("Pink"), loc=tip, scale=(1.6, 2.2, 2.6))

def level3_extras(col, p, z0):
    # tentacles growing from the roof ridge
    for i in range(5):
        y = -17.0 + 8.5 * i
        x = p["rx"] + (3.0 if i % 2 == 0 else -3.0)
        bz = roof_z(x, y, z0, p) - 0.3
        H = 18.0 + 4.0 * math.sin(i)
        A = 5.0 + 2.0 * math.cos(i)
        ph = i * 1.3
        pts, rad = [], []
        for k in range(18):
            t = k / 17.0
            ang = ph + t * 5.0
            pts.append((x + A * t * (math.cos(ang) - math.cos(ph)),
                        y + A * t * (math.sin(ang) - math.sin(ph)),
                        bz + H * t))
            rad.append(1.7 * (1.0 - t) ** 0.8 + 0.12)
        mobj("Tentacle", col, tube_mesh("Tentacle", pts, rad, "Tentacle", seg=12))
        for k in (4, 8, 12):
            px, py, pz = pts[k]
            mobj("Tentacle sucker", col, unit_sphere("Bone"), loc=(px + rad[k] * 0.8, py, pz), scale=(0.55, 0.55, 0.55))
    # tumour clusters with muted sickly-olive pustules on the roof
    for (cx, cy, rr) in ((-20.0, 12.0, 5.0), (17.0, -12.0, 4.4)):
        cz = roof_z(cx, cy, z0, p) + 1.0
        mobj("Tumor big", col, unit_sphere("Tumor"), loc=(cx, cy, cz), scale=(rr, rr, rr * 0.9))
        mobj("Tumor medium", col, unit_sphere("Tumor"), loc=(cx + rr * 0.9, cy - rr * 0.8, cz - 0.6),
             scale=(rr * 0.62, rr * 0.62, rr * 0.55))
        mobj("Tumor small", col, unit_sphere("Tumor"), loc=(cx - rr * 0.8, cy - rr * 0.9, cz - 0.9),
             scale=(rr * 0.42, rr * 0.42, rr * 0.4))
        for k in range(5):
            a = k * 1.26 + cx
            mobj("Pustule", col, unit_sphere("Pustule"),
                 loc=(cx + rr * 0.78 * math.cos(a), cy + rr * 0.78 * math.sin(a), cz + rr * 0.55),
                 scale=(0.9, 0.9, 0.9))
    # slime drips hanging from both eaves
    for sx in (-1, 1):
        for k, y in enumerate((-18.0, -9.0, 2.0, 13.0, 20.0)):
            ez = roof_z(sx * 26.5, y, z0, p) - 0.6
            ln = 3.5 + 1.5 * math.sin(k * 2.1 + sx)
            mobj("Slime drip", col, frustum_mesh("Slime drip", 0.05, 0.8, ln, "Pustule", seg=10),
                 loc=(sx * 26.5, y, ez - ln / 2.0 + 0.2))

def build_shell(n):
    root = bpy.data.collections["Barn_Level_%d" % n]
    for nm in ("L%d | Mutant Shell" % n, "L%d | Added Foundation and Trim" % n):
        old = bpy.data.collections.get(nm)
        if old:
            remove_collection_tree(old)
    col = bpy.data.collections.new("L%d | Mutant Shell" % n)
    root.children.link(col)

    p = ROOFP[n]
    z0 = ZB + 14.0 * n
    wall_base = ZB - 0.2
    door_top = ZB + 11.0  # slightly taller entrance as well as wider
    accent = ACCENT[n][0]
    wall_key = "Wall%d" % n
    roof_key = "Roof%d" % n
    wall_h = z0 - wall_base

    # Squared stone footing and a broad, clean foundation lip.
    box("Barn stone foundation", col, "CliffLight", (51.8, 49.2, 2.0), (0, 0, 0.7))
    box("Barn stone footing", col, "Cliff", (53.2, 50.6, 0.8), (0, 0, 0.0))

    # Side walls. Levels 2 and 3 have a real opening at the upper end of the exterior stairs.
    side_x = {-1: (lambda y, z: -25.55), 1: (lambda y, z: 25.55)}
    for sx in (-1, 1):
        side_entry = (sx == 1 and n in (2, 3))
        if side_entry:
            entry_left = SIDE_ENTRY_CENTER_Y - SIDE_ENTRY_HALF_WIDTH
            entry_right = SIDE_ENTRY_CENTER_Y + SIDE_ENTRY_HALF_WIDTH
            entry_bottom = ZB + 14.0
            entry_top = entry_bottom + SIDE_ENTRY_HEIGHT
            # Wall below the landing/door remains continuous.
            lower_h = entry_bottom - wall_base
            box("Barn long side wall lower", col, wall_key, (1.1, 49.0, lower_h),
                (sx * 25.0, 0.0, wall_base + lower_h / 2.0))
            # Side wall segments to either side of the opening.
            left_len = entry_left + 24.5
            right_len = 24.5 - entry_right
            mid_h = entry_top - entry_bottom
            if left_len > 0.1:
                box("Barn long side wall before stair entry", col, wall_key,
                    (1.1, left_len, mid_h),
                    (sx * 25.0, (-24.5 + entry_left) / 2.0, (entry_bottom + entry_top) / 2.0))
            if right_len > 0.1:
                box("Barn long side wall after stair entry", col, wall_key,
                    (1.1, right_len, mid_h),
                    (sx * 25.0, (entry_right + 24.5) / 2.0, (entry_bottom + entry_top) / 2.0))
            upper_h = z0 - entry_top
            if upper_h > 0.1:
                box("Barn long side wall upper", col, wall_key, (1.1, 49.0, upper_h),
                    (sx * 25.0, 0.0, entry_top + upper_h / 2.0))
        else:
            box("Barn long side wall", col, wall_key, (1.1, 49.0, wall_h),
                (sx * 25.0, 0.0, (wall_base + z0) / 2.0))

        # Heavy corner posts and spaced vertical timber battens.
        for yy in (-24.0, -23.0, -11.0, 0.0, 11.0, 23.0, 24.0):
            width = 0.42 if abs(yy) > 22.5 else 0.28
            box("Side wall timber batten", col, accent, (0.32, width, wall_h),
                (sx * 25.62, yy, (wall_base + z0) / 2.0))
        box("Side wall bottom rail", col, accent, (0.38, 49.5, 0.45),
            (sx * 25.63, 0.0, wall_base + 0.35))
        for floor_i in range(1, n):
            band_z = ZB + 14.0 * floor_i
            if side_entry and floor_i == 1:
                # Split the first-floor belt around the clear doorway threshold.
                for a, b in ((-24.75, SIDE_ENTRY_CENTER_Y - SIDE_ENTRY_HALF_WIDTH),
                             (SIDE_ENTRY_CENTER_Y + SIDE_ENTRY_HALF_WIDTH, 24.75)):
                    if b - a > 0.1:
                        box("Side wall floor band", col, accent, (0.42, b - a, 0.52),
                            (sx * 25.64, (a + b) / 2.0, band_z))
            else:
                box("Side wall floor band", col, accent, (0.42, 49.5, 0.52),
                    (sx * 25.64, 0.0, band_z))
        add_side_planking(col, sx, wall_base, z0, side_entry=side_entry)
        if side_entry:
            add_side_entry_frame(col, n, wall_base, accent)

    # Reconstruct the interior floors from scratch: no source floor slabs, stalls, or
    # pen/fence structures remain. Ground and usable first floors get clean plank decks.
    add_elevated_floor_planks(col, floor_index=0, ladder_opening=False)
    add_display_walkways(col, floor_index=0)
    add_display_pads(col, floor_index=0)
    if n in (2, 3):
        add_elevated_floor_planks(col, floor_index=1, ladder_opening=False)
        add_first_floor_access_path(col, n)
        add_display_walkways(col, floor_index=1)
        add_display_pads(col, floor_index=1)
    if n == 3:
        # The top floor gets its own display pads and access aisle. Keep the ladder hatch
        # clear: its x/y footprint sits outside all pad footprints.
        add_elevated_floor_planks(col, floor_index=2, ladder_opening=True)
        add_display_walkways(col, floor_index=2)
        add_display_pads(col, floor_index=2)

    # Gable ends are assembled from straight rectangular wall sections plus a triangular top.
    for sy in (-1, 1):
        y = sy * 24.5
        # Keep the widened entrance centred on x=0, with clean wall edges at each jamb.
        side_width = 25.5 - ENTRANCE_HALF_WIDTH
        side_center = (25.5 + ENTRANCE_HALF_WIDTH) / 2.0
        box("Gable end left wall section", col, wall_key, (side_width, 1.1, wall_h),
            (-side_center, y, (wall_base + z0) / 2.0))
        box("Gable end right wall section", col, wall_key, (side_width, 1.1, wall_h),
            (side_center, y, (wall_base + z0) / 2.0))
        header_h = max(0.1, z0 - door_top)
        box("Gable end wall above entrance", col, wall_key, (51.0, 1.1, header_h),
            (0.0, y, (door_top + z0) / 2.0))
        add_gable_triangle(col, sy, z0, wall_key)
        add_end_wall_planking(col, sy, wall_base, door_top, z0)
        add_gable_planking(col, sy, z0, window_on_face=(sy == -1))
        add_doorway(col, sy, wall_base, door_top, accent)
        # Levels 2 and 3 get extra timber-stick framing on both end faces.
        # Level 1 is left unchanged so its sneaker-barn silhouette stays distinct.
        if n in (2, 3):
            add_wooden_stick_bracing(col, n, sy, wall_base, z0)
        # Exactly one large centred glass window on the front gable only.
        # No extra upper-storey or rear windows, keeping the silhouette clean.
        if sy == -1:
            add_gable_window(col, sy, z0, accent, level=n)
        # End wall corner posts and the gable/eave timber belt.
        for xx in (-24.8, 24.8):
            box("End wall corner post", col, accent, (0.42, 0.36, wall_h),
                (xx, sy * 25.18, (wall_base + z0) / 2.0))
        box("End wall eave beam", col, accent, (51.4, 0.42, 0.48), (0.0, sy * 25.18, z0))

    build_roof(col, n, p, roof_key, accent)

    # Keep distinct brainrot identity pieces, but keep the first entrance free of shoe props.
    if n == 1:
        level1_extras(col, p, z0)
    elif n == 2:
        level2_extras(col, p, z0, side_x)
    else:
        level3_extras(col, p, z0)
        add_interior_ladder(col)
    if n in (2, 3):
        add_exterior_staircase(col, n)
    return col

def nested_collections(root):
    """Yield all descendant collections under root, depth first."""
    for child in list(root.children):
        yield child
        yield from nested_collections(child)


def is_generated_shell_collection(coll):
    nm = coll.name.lower()
    return "mutant shell" in nm or "added foundation and trim" in nm


def object_bounds_in_source(obj):
    """Return approximate source-barn-local bounds, including collection instances."""
    try:
        points = []
        if getattr(obj, "instance_type", "NONE") == "COLLECTION" and obj.instance_collection:
            for child in all_objects(obj.instance_collection):
                try:
                    transform = obj.matrix_world @ child.matrix_world
                    points.extend(transform @ Vector(corner) for corner in child.bound_box)
                except Exception:
                    continue
        if not points:
            points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        return (min(v.x for v in points), max(v.x for v in points),
                min(v.y for v in points), max(v.y for v in points))
    except Exception:
        loc = obj.matrix_world.translation
        return (loc.x, loc.x, loc.y, loc.y)


def object_bounds_3d_in_source(obj):
    """Return approximate source-local/world bounds for meshes and collection instances."""
    try:
        points = []
        if getattr(obj, "instance_type", "NONE") == "COLLECTION" and obj.instance_collection:
            for child in all_objects(obj.instance_collection):
                try:
                    transform = obj.matrix_world @ child.matrix_world
                    points.extend(transform @ Vector(corner) for corner in child.bound_box)
                except Exception:
                    continue
        if not points:
            points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        return (min(v.x for v in points), max(v.x for v in points),
                min(v.y for v in points), max(v.y for v in points),
                min(v.z for v in points), max(v.z for v in points))
    except Exception:
        loc = obj.matrix_world.translation
        return (loc.x, loc.x, loc.y, loc.y, loc.z, loc.z)


def delete_object_tree(obj):
    """Delete an object and its children so grouped crop/stair assets do not leave pieces behind."""
    try:
        names = [obj.name] + [child.name for child in getattr(obj, "children_recursive", [])]
    except Exception:
        names = [obj.name]
    # Re-fetch by name as each deletion invalidates the corresponding Blender object reference.
    for name in reversed(list(dict.fromkeys(names))):
        item = bpy.data.objects.get(name)
        if item is not None:
            bpy.data.objects.remove(item, do_unlink=True)


def rebuild_source_interiors_empty():
    """Remove legacy interior floor slabs, pens, stalls and fence geometry before rebuilding decks.

    Only source objects in the barn interior volume are targeted. The new shell collection is
    excluded, and exterior stairs (outside the footprint) plus perimeter walls/roof are retained.
    """
    removed = 0
    floor_tokens = ("floor", "deck", "slab", "platform", "walkway", "plank", "board", "loft")
    for n in LEVELS:
        root = bpy.data.collections.get("Barn_Level_%d" % n)
        if root is None:
            continue
        candidates = []
        for coll in [root] + list(nested_collections(root)):
            if is_generated_shell_collection(coll):
                continue
            for obj in list(coll.objects):
                if obj.type not in {"MESH", "CURVE", "SURFACE", "FONT", "EMPTY"}:
                    continue
                if any(is_generated_shell_collection(uc) for uc in getattr(obj, "users_collection", [])):
                    continue
                try:
                    x0, x1, y0, y1, z0, z1 = object_bounds_3d_in_source(obj)
                except Exception:
                    continue
                name_chain = (obj.name + " " + " ".join(c.name for c in getattr(obj, "users_collection", []))).lower().replace("_", " ")
                interior_xy = (x0 >= -24.0 and x1 <= 24.0 and y0 >= -23.5 and y1 <= 23.5)
                floor_like = any(tok in name_chain for tok in floor_tokens) and (z1 - z0) < 8.0 and z0 < ZB + 30.0
                # Remove all bounded interior props, including generically named fence posts,
                # plus broad floor/deck slabs whose names clearly identify their function.
                if interior_xy and z1 > ZB - 1.0 and z0 < ZB + 42.0:
                    candidates.append(obj.name)
                elif floor_like and x0 > -27.0 and x1 < 27.0 and y0 > -26.0 and y1 < 26.0:
                    candidates.append(obj.name)
        for name in dict.fromkeys(candidates):
            obj = bpy.data.objects.get(name)
            if obj is None:
                continue
            # Guard against deleting generated shell parts through multi-collection links.
            if any(is_generated_shell_collection(uc) for uc in getattr(obj, "users_collection", [])):
                continue
            log("Removing legacy interior geometry for floor rebuild: " + obj.name)
            delete_object_tree(obj)
            removed += 1
    log("Legacy interior/floor rebuild cleanup removed %d source objects" % removed)


def adjust_source_interiors():
    """Remove old farm plots and their fences; clear source stairs from Levels 2/3."""
    farm_collection_tokens = ("farm", "crop", "plot", "field", "garden", "plant bed", "planter",
                              "harvest", "cultivat", "soil bed", "paddock", "corral")
    plot_object_tokens = ("farm", "plot", "crop", "field plot", "field bed", "plant bed", "planter",
                          "garden plot", "garden bed", "wheat", "corn", "vegetable", "harvest plot",
                          "cultivat", "soil bed", "paddock", "corral")
    fence_tokens = ("fence", "picket fence", "farm rail", "plot rail", "pen rail", "paddock rail", "corral")
    stair_tokens = ("stair", "staircase", "stairway", "stairwell", "steps", "step assembly", "stair flight", "ladder")
    farm_removed = 0
    fence_removed = 0
    stairs_removed = 0

    def name_chain(obj):
        bits = [obj.name.lower().replace("_", " ")]
        parent = obj.parent
        seen = set()
        while parent is not None and parent.name not in seen:
            seen.add(parent.name)
            bits.append(parent.name.lower().replace("_", " "))
            parent = parent.parent
        for coll in getattr(obj, "users_collection", []):
            bits.append(coll.name.lower().replace("_", " "))
        return " | ".join(bits)

    def inside_barn_footprint(obj):
        try:
            min_x, max_x, min_y, max_y = object_bounds_in_source(obj)
            return (min_x >= -27.0 and max_x <= 27.0 and
                    min_y >= -26.0 and max_y <= 26.0)
        except Exception:
            return False

    for n in LEVELS:
        root = bpy.data.collections.get("Barn_Level_%d" % n)
        if root is None:
            continue

        # Delete source collections explicitly representing fields, plots, pens or fences.
        for coll_name in [c.name for c in nested_collections(root)]:
            coll = bpy.data.collections.get(coll_name)
            if coll is None or is_generated_shell_collection(coll):
                continue
            nm = coll.name.lower().replace("_", " ")
            is_farm_collection = any(tok in nm for tok in farm_collection_tokens)
            is_fence_collection = "fence" in nm or "paddock" in nm or "corral" in nm
            is_stair_collection = (n in (2, 3) and any(tok in nm for tok in stair_tokens))
            if is_stair_collection:
                log("Removing old interior stair collection: " + coll.name)
                remove_collection_tree(coll)
                stairs_removed += 1
            elif is_fence_collection:
                log("Removing old interior fence collection: " + coll.name)
                remove_collection_tree(coll)
                fence_removed += 1
            elif is_farm_collection:
                log("Removing old interior farm/plot collection: " + coll.name)
                remove_collection_tree(coll)
                farm_removed += 1

        # Remove remaining individually named farm/crop/fence objects, including child parts.
        # Generic fence pieces are only removed when their bounds are inside the barn footprint.
        candidate_names = []
        current_collections = [root.name] + [c.name for c in nested_collections(root)]
        for coll_name in current_collections:
            coll = bpy.data.collections.get(coll_name)
            if coll is None or is_generated_shell_collection(coll):
                continue
            for obj in list(coll.objects):
                chain = name_chain(obj)
                is_farm_piece = any(tok in chain for tok in plot_object_tokens)
                is_fence_piece = any(tok in chain for tok in fence_tokens) and inside_barn_footprint(obj)
                is_stair_piece = n in (2, 3) and any(tok in chain for tok in stair_tokens)
                if is_farm_piece or is_fence_piece or is_stair_piece:
                    candidate_names.append((obj.name, is_farm_piece, is_fence_piece, is_stair_piece))

        # Prefer removing the highest matching ancestor once, so all grouped components disappear.
        to_remove = {}
        for obj_name, is_farm_piece, is_fence_piece, is_stair_piece in candidate_names:
            obj = bpy.data.objects.get(obj_name)
            if obj is None:
                continue
            current = obj
            matched = False
            while current is not None:
                chain = name_chain(current)
                current_is_stair = n in (2, 3) and any(tok in chain for tok in stair_tokens)
                current_is_fence = any(tok in chain for tok in fence_tokens) and inside_barn_footprint(current)
                current_is_farm = any(tok in chain for tok in plot_object_tokens)
                if current_is_stair or current_is_fence or current_is_farm:
                    to_remove[current.name] = (current_is_farm, current_is_fence, current_is_stair)
                    matched = True
                    # Keep moving upward to remove a clearly named group root too.
                    parent = current.parent
                    if parent is None:
                        break
                    parent_chain = name_chain(parent)
                    parent_matches = ((n in (2, 3) and any(tok in parent_chain for tok in stair_tokens)) or
                                      (any(tok in parent_chain for tok in fence_tokens) and inside_barn_footprint(parent)) or
                                      any(tok in parent_chain for tok in plot_object_tokens))
                    if parent_matches:
                        current = parent
                        continue
                    break
                current = current.parent
            if not matched:
                to_remove[obj.name] = (is_farm_piece, is_fence_piece, is_stair_piece)

        # Remove unique candidates in order from group roots to children.
        for obj_name, flags in sorted(to_remove.items(), key=lambda it: it[0].count(".")):
            obj = bpy.data.objects.get(obj_name)
            if obj is None:
                continue
            log("Removing legacy interior object/group: " + obj.name)
            delete_object_tree(obj)
            farm_removed += int(flags[0])
            fence_removed += int(flags[1])
            stairs_removed += int(flags[2])

    log("Interior cleanup complete: %d farm/plot groups, %d fence groups, and %d old stair/ladder groups removed" %
        (farm_removed, fence_removed, stairs_removed))


def source_collections_without_generated(root):
    """Yield source collections but skip regenerated shell/trim trees."""
    yield root
    for child in list(root.children):
        if is_generated_shell_collection(child):
            continue
        yield from source_collections_without_generated(child)


def remove_legacy_structures_over_display_pads():
    """Remove residual source meshes/instances that occupy the four green-pad footprints."""
    # Slightly expanded pad footprints catch rails, posts, stalls, and small wooden frames
    # that older name-based farm/fence cleanup missed. Large building walls/floors are excluded.
    pad_regions = [
        (-18.65, -10.35, -11.30, -2.70),
        (-18.65, -10.35,  4.20, 12.80),
        ( 10.35,  18.65, -11.30, -2.70),
        ( 10.35,  18.65,  4.20, 12.80),
    ]
    deleted_total = 0
    for n in LEVELS:
        root = bpy.data.collections.get("Barn_Level_%d" % n)
        if root is None:
            continue
        candidates = []
        seen = set()
        for coll in source_collections_without_generated(root):
            for obj in list(coll.objects):
                if obj.name in seen or obj.name.startswith("Plain green display pad"):
                    continue
                if obj.type not in {"MESH", "CURVE", "SURFACE", "META", "EMPTY"}:
                    continue
                # Ignore anything already belonging to a newly generated shell.
                if any(is_generated_shell_collection(uc) for uc in getattr(obj, "users_collection", [])):
                    continue
                seen.add(obj.name)
                bounds = object_bounds_3d_in_source(obj)
                x0, x1, y0, y1, z0, z1 = bounds
                sx, sy = x1 - x0, y1 - y0
                # The legacy props must rise above the pad but start in the ground-floor space.
                if z1 <= ZB + 0.85 or z0 >= ZB + 14.0:
                    continue
                # Keep whole-barn shells, floors, roofs and long external walls intact.
                if sx > 24.0 or sy > 20.0:
                    continue
                hit = any(x1 >= px0 and x0 <= px1 and y1 >= py0 and y0 <= py1
                          for px0, px1, py0, py1 in pad_regions)
                if hit:
                    candidates.append(obj.name)
        for name in candidates:
            obj = bpy.data.objects.get(name)
            if obj is not None:
                log("Removing leftover structure over display pad: " + obj.name)
                delete_object_tree(obj)
                deleted_total += 1
    log("Removed %d leftover objects/assemblies over green display pads" % deleted_total)


def clear_mesh_geometry_over_pad_volumes(mesh_obj, pad_regions):
    """Remove faces inside pad footprints above the ground slab, even in merged source meshes."""
    if mesh_obj is None or mesh_obj.type != "MESH" or mesh_obj.data is None or not mesh_obj.data.polygons:
        return 0
    try:
        x0, x1, y0, y1, z0, z1 = object_bounds_3d_in_source(mesh_obj)
        if z1 <= ZB + 0.80 or z0 >= ZB + 14.0:
            return 0
        if not any(x1 >= px0 and x0 <= px1 and y1 >= py0 and y0 <= py1
                   for px0, px1, py0, py1 in pad_regions):
            return 0
        if mesh_obj.data.users > 1:
            mesh_obj.data = mesh_obj.data.copy()
        bm = bmesh.new()
        bm.from_mesh(mesh_obj.data)
        if not bm.faces:
            bm.free()
            return 0
        world_matrix = mesh_obj.matrix_world.copy()
        bmesh.ops.transform(bm, matrix=world_matrix, verts=list(bm.verts))

        # Split each footprint boundary so even a large merged mesh can be cleared precisely.
        planes = []
        for px0, px1, py0, py1 in pad_regions:
            planes.extend([
                (Vector((px0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0))),
                (Vector((px1, 0.0, 0.0)), Vector((1.0, 0.0, 0.0))),
                (Vector((0.0, py0, 0.0)), Vector((0.0, 1.0, 0.0))),
                (Vector((0.0, py1, 0.0)), Vector((0.0, 1.0, 0.0))),
            ])
        for plane_co, plane_no in planes:
            geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=plane_co, plane_no=plane_no,
                                   dist=0.0001, clear_inner=False, clear_outer=False)
        bm.normal_update()

        lower_z = ZB + 0.80
        upper_z = ZB + 14.0 - 0.30
        faces_to_remove = []
        for face in list(bm.faces):
            center = face.calc_center_median()
            if not (lower_z < center.z < upper_z):
                continue
            if any(px0 + 1e-4 < center.x < px1 - 1e-4 and
                   py0 + 1e-4 < center.y < py1 - 1e-4
                   for px0, px1, py0, py1 in pad_regions):
                faces_to_remove.append(face)
        removed = len(faces_to_remove)
        if removed:
            bmesh.ops.delete(bm, geom=faces_to_remove, context="FACES")
            # Remove loose remnants left by clearing a merged stall/fence mesh.
            loose_edges = [e for e in bm.edges if not e.link_faces]
            if loose_edges:
                bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
            loose_verts = [v for v in bm.verts if not v.link_edges]
            if loose_verts:
                bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
            bmesh.ops.transform(bm, matrix=world_matrix.inverted_safe(), verts=list(bm.verts))
            bm.to_mesh(mesh_obj.data)
            mesh_obj.data.update()
        bm.free()
        return removed
    except Exception as exc:
        try:
            bm.free()
        except Exception:
            pass
        log("Could not clear merged pad obstruction in %s: %s" % (mesh_obj.name, str(exc)[:100]))
        return 0


def clear_mesh_obstructions_over_display_pads():
    """Geometry-based fallback for wooden frames merged into a larger source mesh."""
    pad_regions = [
        (-18.40, -10.60, -11.00, -3.00),
        (-18.40, -10.60,   4.50, 12.50),
        ( 10.60,  18.40, -11.00, -3.00),
        ( 10.60,  18.40,   4.50, 12.50),
    ]
    removed_faces = 0
    edited_objects = set()
    for n in LEVELS:
        root = bpy.data.collections.get("Barn_Level_%d" % n)
        if root is None:
            continue
        for coll in source_collections_without_generated(root):
            for obj in list(coll.objects):
                if obj.name in edited_objects or obj.type != "MESH":
                    continue
                if any(is_generated_shell_collection(uc) for uc in getattr(obj, "users_collection", [])):
                    continue
                count = clear_mesh_geometry_over_pad_volumes(obj, pad_regions)
                if count:
                    log("Cleared %d faces of old structure over display pads in %s" % (count, obj.name))
                    removed_faces += count
                    edited_objects.add(obj.name)
    log("Merged-mesh display-pad cleanup removed %d faces" % removed_faces)


def cut_horizontal_opening(mesh_obj, x_min, x_max, y_min, y_max, target_z, half_depth=5.0):
    """Cut a rectangular opening through a horizontal source floor mesh, in world coordinates."""
    if mesh_obj is None or mesh_obj.type != "MESH" or mesh_obj.data is None:
        return False
    if len(mesh_obj.data.polygons) == 0:
        return False
    try:
        if mesh_obj.data.users > 1:
            mesh_obj.data = mesh_obj.data.copy()
        bm = bmesh.new()
        bm.from_mesh(mesh_obj.data)
        if not bm.faces:
            bm.free()
            return False
        world_matrix = mesh_obj.matrix_world.copy()
        bmesh.ops.transform(bm, matrix=world_matrix, verts=list(bm.verts))

        # Split large floor faces at the four opening boundaries, then remove only horizontal
        # faces inside the opening at the requested floor height.
        planes = [
            (Vector((x_min, 0.0, 0.0)), Vector((1.0, 0.0, 0.0))),
            (Vector((x_max, 0.0, 0.0)), Vector((1.0, 0.0, 0.0))),
            (Vector((0.0, y_min, 0.0)), Vector((0.0, 1.0, 0.0))),
            (Vector((0.0, y_max, 0.0)), Vector((0.0, 1.0, 0.0))),
        ]
        for plane_co, plane_no in planes:
            geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=plane_co, plane_no=plane_no,
                                   dist=0.0001, clear_inner=False, clear_outer=False)

        bm.normal_update()
        z_min, z_max = target_z - half_depth, target_z + half_depth
        faces_to_remove = []
        for face in list(bm.faces):
            center = face.calc_center_median()
            if (x_min + 1e-4 < center.x < x_max - 1e-4 and
                y_min + 1e-4 < center.y < y_max - 1e-4 and
                z_min <= center.z <= z_max and abs(face.normal.z) >= 0.60):
                faces_to_remove.append(face)
        if not faces_to_remove:
            bm.free()
            return False
        bmesh.ops.delete(bm, geom=faces_to_remove, context="FACES")
        loose_edges = [edge for edge in bm.edges if not edge.link_faces]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
        loose_verts = [vert for vert in bm.verts if not vert.link_edges]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
        inv_world = world_matrix.inverted_safe()
        bmesh.ops.transform(bm, matrix=inv_world, verts=list(bm.verts))
        bm.to_mesh(mesh_obj.data)
        bm.free()
        mesh_obj.data.update()
        return True
    except Exception as exc:
        try:
            bm.free()
        except Exception:
            pass
        log("Could not cut source floor opening in %s: %s" % (mesh_obj.name, str(exc)[:100]))
        return False


def cut_source_floor_openings_for_access():
    """Cut a full-thickness ladder hatch in Level 3's original upper-floor geometry.

    The replacement plank deck also leaves the same aperture open. Source floors may be
    separate thin slabs or part of a larger merged building mesh, so this routine handles
    both cases. If a separate, thin source deck refuses the mesh cut, it is hidden because
    the generated planks fully replace its walking surface.
    """
    cut_count = 0
    hidden_decks = 0
    floor_tokens = ("floor", "deck", "slab", "platform", "walkway", "plank", "board")
    root3 = bpy.data.collections.get("Barn_Level_3")
    if root3 is None:
        log("Level 3 source collection not found; generated deck will still have an open hatch")
        return

    x0, x1 = LADDER_HOLE_X0, LADDER_HOLE_X1
    y0, y1 = LADDER_HOLE_Y0, LADDER_HOLE_Y1
    z_target = ZB + 28.0
    z_half = 5.0
    handled = set()

    for coll in source_collections_without_generated(root3):
        for obj in list(coll.objects):
            if obj.name in handled or obj.type != "MESH" or obj.data is None:
                continue
            if any(is_generated_shell_collection(uc) for uc in getattr(obj, "users_collection", [])):
                continue
            bounds = object_bounds_3d_in_source(obj)
            bx0, bx1, by0, by1, bz0, bz1 = bounds
            if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
                continue
            if bz0 > z_target + z_half or bz1 < z_target - z_half:
                continue
            span_x, span_y, span_z = bx1 - bx0, by1 - by0, bz1 - bz0
            chain = (obj.name + " " + " ".join(c.name for c in getattr(obj, "users_collection", []))).lower()
            named_floor = any(tok in chain for tok in floor_tokens)
            thin_horizontal_mesh = (span_x >= 0.35 and span_y >= 0.35 and span_z <= 6.5 and
                                    abs((bz0 + bz1) / 2.0 - z_target) <= 3.2)
            merged_building_mesh = (span_x >= 30.0 and span_y >= 30.0 and
                                    bz0 < z_target and bz1 > z_target)
            broad_horizontal_deck = (span_x >= 12.0 and span_y >= 12.0 and span_z <= 6.5 and
                                     abs((bz0 + bz1) / 2.0 - z_target) <= 3.2)
            if not (named_floor or thin_horizontal_mesh or merged_building_mesh or broad_horizontal_deck):
                continue
            handled.add(obj.name)
            if cut_horizontal_opening(obj, x0, x1, y0, y1, z_target, z_half):
                log("Cut full-thickness ladder hatch through source floor mesh: " + obj.name)
                cut_count += 1
                continue

            # A separate thin slab is safely replaced by the newly generated plank deck.
            # Hide only thin horizontal decks; never hide a merged whole-building mesh here.
            if (span_x >= 12.0 and span_y >= 12.0 and span_z <= 4.5 and
                abs((bz0 + bz1) / 2.0 - z_target) <= 2.5 and not merged_building_mesh):
                obj.hide_render = True
                obj.hide_viewport = True
                hidden_decks += 1
                log("Hid separate source deck; generated open plank hatch replaces it: " + obj.name)
            else:
                log("Could not cut source hatch in %s; generated plank hatch is still open" % obj.name)

    log("Source ladder hatch result: %d mesh cut(s), %d separate deck(s) hidden" %
        (cut_count, hidden_decks))

def archive_originals(lib, n):
    arch = bpy.data.collections.get("Barn_Original_Shells") or bpy.data.collections.new("Barn_Original_Shells")
    if arch.name not in lib.children:
        lib.children.link(arch)
    root = bpy.data.collections["Barn_Level_%d" % n]
    for nm in ("L%d | Walls Windows and Open Doors" % n, "L%d | Detachable Roof" % n):
        c = bpy.data.collections.get(nm)
        if c:
            if c.name in root.children:
                root.children.unlink(c)
            if c.name not in arch.children:
                arch.children.link(c)

def build_yard_props(lib):
    name = "Barn_Yard_Props"
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    lib.children.link(col)
    # (hay bales sit beside the entrance; kept away from the sneakers at x = -21 and 10)
    for (x, y) in ((-24.5, -44.0), (15.5, -44.0)):
        box("Hay bale", col, "Hay", (3.4, 2.0, 1.7), (x, y, 0.85))
        box("Hay bale", col, "Hay", (3.4, 2.0, 1.7), (x + 3.6, y + 0.3, 0.85), (0, 0, 0.12))
        box("Hay bale", col, "Hay", (3.4, 2.0, 1.7), (x + 1.8, y + 0.1, 2.55), (0, 0, -0.08))
    return col

# ---------------- 5. place on farms ----------------
def upsert_instance(name, coll, host, pe, loc, rot, scale):
    inst = bpy.data.objects.get(name)
    if inst is None:
        inst = bpy.data.objects.new(name, None)
        inst.empty_display_type = "PLAIN_AXES"
        inst.empty_display_size = 5.0
        host.objects.link(inst)
    elif host.name not in [c.name for c in inst.users_collection]:
        host.objects.link(inst)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = coll
    inst.parent = pe
    inst.matrix_parent_inverse = Matrix.Identity(4)
    inst.location = loc
    inst.rotation_euler = rot
    inst.scale = (scale, scale, scale)
    try:
        inst.hide_set(False)
    except Exception:
        pass
    inst.hide_render = False
    inst.hide_viewport = False
    return inst

def place_barns(props):
    done = 0
    for i in range(1, 7):
        pe = bpy.data.objects.get("Barn_Placement_Farm_%02d" % i)
        host = bpy.data.collections.get("Farm_%02d_Barn_Placement" % i)
        if not pe or not host:
            log("Farm %02d: placement empty/collection not found - skipped" % i)
            continue
        old = bpy.data.objects.get("Farm_%02d_Barn_Yard_Props" % i)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        # Keep only this progression stage on each farm.
        for obsolete_level in (1, 2, 3):
            if obsolete_level == 1:
                continue
            for obsolete_name in (
                "Farm_%02d_Barn_Level_%d" % (i, obsolete_level),
                "Farm_%02d_Barn_Yard_Props_%d" % (i, obsolete_level),
            ):
                obsolete = bpy.data.objects.get(obsolete_name)
                if obsolete:
                    bpy.data.objects.remove(obsolete, do_unlink=True)
        for n in LEVELS:
            # Compensate for the collection origin and keep the entrance aligned to the pathway.
            lx = -5.5 + 5.5 * SCALE + BARN_SHIFT_X
            lean = math.radians(LEAN_DEG.get(n, 0.0))
            upsert_instance("Farm_%02d_Barn_Level_%d" % (i, n), bpy.data.collections["Barn_Level_%d" % n],
                            host, pe, (lx, 0.0, BARN_Z), (0.0, lean, 0.0), SCALE)
            if props:
                upsert_instance("Farm_%02d_Barn_Yard_Props_%d" % (i, n), props,
                                host, pe, (lx, 0.0, BARN_Z), (0.0, 0.0, 0.0), SCALE)
        done += 1
    log("Placed one expanded Level 1 barn, pathway-aligned, on each of %d farms" % done)

# ---------------- run ----------------
def popup(lines, title):
    def draw(self, ctx):
        for l in lines:
            self.layout.label(text=l)
    bpy.context.window_manager.popup_menu(draw, title=title, icon="INFO")

def main():
    try:
        lib = import_barns()
        setup_materials()
        rebuild_source_interiors_empty()
        adjust_source_interiors()
        remove_legacy_structures_over_display_pads()
        clear_mesh_obstructions_over_display_pads()
        cut_source_floor_openings_for_access()
        for n in LEVELS:
            try:
                build_shell(n)
                archive_originals(lib, n)
                log("Level %d mutant shell built" % n)
            except Exception:
                err = traceback.format_exc()
                print(err)
                log("Level %d FAILED: %s" % (n, err.strip().splitlines()[-1][:80]))
        props = build_yard_props(lib)
        place_barns(props)
        bpy.context.view_layer.update()
        log("Done. Built the expanded red plank Level 1 barn only, aligned with the pathway. Press Ctrl+S to save.")
        popup(REPORT[-5:], "Expanded Red Plank Barn")
    except Exception:
        err = traceback.format_exc()
        print(err)
        popup(["Failed - see Window > Toggle System Console", err.strip().splitlines()[-1][:90]], "Barn builder error")

main()
