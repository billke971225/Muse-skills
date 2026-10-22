# Blender Studio Renders — product-grade stills for single-product DTC pages

Produce **studio-quality product renders** from a Blender model with nothing but
Python (`bpy`): a three-point light rig plus an overhead softbox, a seamless
white sweep, real contact shadows, optional depth of field, and a scripted
shot list that outputs a full set of hero / detail / color-variant images in
one batch run.

This exists because of a hard product rule: **a product page must show a
finished-looking product, not a grey model or a flat-lit viewport screenshot.**
Modeling is the means (it enables rotation, color swaps, and part articulation
for interactive views); the studio render is what the customer actually sees.
Every "product exposure" slot on the page — hero, feature close-ups, variant
swatches — gets a studio render. Interactive 3D, if any, is lit to the same
standard.

Companion template: `scripts/studio_render.py`. Copy it next to your model,
fill in the `CONFIG` block, run headless:

```bash
blender --background --python studio_render.py -- test   # one cheap frame: judge the light
blender --background --python studio_render.py -- all    # the full shot list
```

Always run `test` first. Lighting is judged on a real render, never on
viewport shading — and on a CPU-only box every full-res frame costs minutes.

## Workflow

1. **Model (or import) the product in real-world-ish units**, parts as separate
   objects with semantic names (`body`, `grip`, `shaft`, `knob`, …) and one
   material per part. The shot script drives parts and materials by name:
   color variants are material swaps, "in-use" poses are part offsets.
2. **Parent all parts under one `PRODUCT` root empty** and lift the root so the
   product's lowest point sits on the ground plane (z = 0). Every shot then
   shares one stage.
3. **Build the stage**: an oversized ground plane with a near-white matte
   material (≈ sRGB 0.97, roughness 0.9) and a white world background
   (strength ≈ 1.6). With Cycles this reads as an infinite white sweep, and
   the ground catches a true contact shadow that grounds the product.
4. **Rig the lights** (below), all aimed at the product's visual center.
5. **Define the shot list** as data — name, variant, camera location, target,
   lens, part offsets, optional f-stop — then batch-render. Adding an angle
   or a colorway is one line, not a new scene.
6. **Render a test frame** at reduced resolution, judge exposure/highlights,
   adjust light energy, then run the full set.

## The light rig (starting point that shipped)

Area lights only — they are what makes a render read as "studio":

| Light | Position | Energy | Size | Job |
|---|---|---|---|---|
| Key | (15, -13, 21) | 1600 | 5 | Main light. Smaller size = harder, more directional modeling |
| Fill | (-15, 11, 13) | 150 | 9 | ~10× weaker than key; lifts shadows without flattening |
| Rim | (-7, 15, 19) | 1500 | 7 | Strong back/edge light; separates dark products from the background |
| Top softbox | (0, 2, 32) | 200 | 12 | Big overhead source; the long soft highlight that sells glossy plastic/metal |

Rules of thumb learned the hard way:

- **Energy ratios matter more than absolute values.** Key:Fill ≈ 10:1. If the
  product looks flat, weaken the fill before touching the key.
- **Dark products need the rim**, not more key. A near-black body on white is
  sold by its edge highlight.
- **Softbox size = highlight softness.** The top light's reflection streak on
  curved surfaces is the single biggest "studio" cue; make it big and close.
- Aim every light at the product center (~ mid-height), not at the floor.

## Camera & depth of field

- **50 mm** for hero 3/4, side, and top shots: natural perspective, no
  wide-angle product distortion.
- **85 mm** for detail shots (mechanism close-up, logo/badge macro): compresses
  perspective and flatters small parts.
- Camera positions (product ≈ 16 units tall, centered at origin):
  hero 3/4 at (19, -23, 14) → target (0.5, 0, 7.5); side at (3, -30, 9);
  straight top at (0.5, -1, 36) aimed down.
- **Depth of field**: enable `cam.data.dof`, focus on the detail part (or set
  focus distance), aperture f/2.8–f/5.6 on 85 mm detail shots only. Hero shots
  stay fully sharp — a blurry hero reads as a mistake, not as art.
- View transform **Standard** with a touch of exposure (≈ +0.1): filmic curves
  mute the white sweep and dull saturated colorways; Standard keeps product
  colors honest against the real object.

## Materials

- Principled BSDF, Metallic 0 for plastics; per-part roughness: body ≈ 0.35,
  grips/seams lower-sat darker values. Resist the urge to make everything
  glossy — roughness contrast between parts is what reads as "real object".
- **Color variants are value swaps on named materials**, defined as dicts:
  a base "dark" set, then per-variant overrides for the two hero materials
  (body + grip) inheriting the rest. Five colorways = five dicts, zero new
  geometry.

## Shot list pattern (the set that shipped: 10 frames)

1. Hero 3/4, base color, 50 mm
2. Side profile, base color, 50 mm
3. Top-down, base color, 50 mm
4. Mechanism detail, 85 mm, part articulated (extended/open state)
5. Badge/logo macro, 85 mm
6. Full product in "in-use" pose, 50 mm
7–10. Hero 3/4 repeated per additional colorway

Output: square 1200×1200 PNGs for finals, 800×800 for the lighting test.

## Using the renders on the page

- Hero slot: the 3/4 hero render, full-bleed. It must look like a photo a
  customer could have taken in a studio — if it reads as "3D", re-light, don't
  ship.
- Feature sections: the detail/macro renders, one per feature claim.
- Variant picker: the per-colorway 3/4 renders — because they come from one
  rig and one camera, swapping them under the picker is pixel-consistent.
- Keep the live/interactive 3D (if the page has any) for rotation and color
  interaction only, lit to match the renders as closely as possible.

## Rendering on a GPU-less, headless Linux VM (read this before debugging)

This workflow was built and run on a 2-core cloud VM with **no GPU, no
display, and no `/dev/dri`**. That environment has sharp edges:

- **Eevee will not save you.** Eevee needs an EGL/OpenGL context. On a VM
  image where the mesa/EGL packages were wiped (e.g. after a VM rebuild,
  `libegl1` goes missing), Blender either crashes at startup or starts but
  cannot create the EGL context, and Eevee renders fail. Extracting the EGL
  shared libraries by hand can get Blender to *launch*, but rendering still
  crashes — a partial sysroot is a dead end.
- **The reliable path is Cycles on CPU**:
  ```python
  scn.render.engine = 'CYCLES'
  scn.cycles.device = 'CPU'
  scn.cycles.samples = 48            # 40–48 is the sweet spot with denoising
  scn.cycles.use_denoising = True
  scn.cycles.denoiser = 'OPENIMAGEDENOISE'
  ```
  40–48 samples + OpenImageDenoise is indistinguishable from a long render for
  still product shots, and it is the difference between "overnight" and
  "coffee break".
- **Cost**: on 2 CPU cores, a 1200×1200 frame at 48 samples takes roughly
  **1–5 minutes**. A 10-shot set is a batch job — start it, go do something
  else, check the output directory.
- **The real fix** (when you control the box) is reinstalling the full mesa
  stack so EGL exists again; treat Cycles-CPU as the production workaround,
  not a stopgap you apologize for — the output quality is the same for stills.
- Run everything with `blender --background --python ...`. No X server, no
  viewport, no problem: Cycles CPU never touches the display stack.

### Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| Blender crashes instantly on the VM | EGL/mesa packages wiped by an image rebuild | Don't chase it — switch the script to Cycles CPU as above |
| Blender starts with extracted `.so` libs but render still dies | Partial EGL sysroot can't build a real context | Same: Cycles CPU; or reinstall the full mesa stack |
| Render looks flat / "CGI" | Fill too strong, rim missing, softbox too small | Restore ~10:1 key:fill, strong rim, enlarge top light |
| White background looks grey | World strength too low, or filmic view transform | World ≈ 1.6, view transform Standard |
| Colorway looks wrong vs the real product | Judging by viewport/material preview | Judge only the denoised test render at final settings |
| Detail shot's subject is soft | DOF focus object/distance not set on the detail part | Set focus explicitly per detail shot; heroes stay DOF-off |

## Don'ts

- Don't ship viewport screenshots or grey-model turntables as product imagery.
- Don't add a shot by hand in the GUI — add a line to the shot list so the set
  stays reproducible.
- Don't judge lighting from the material-preview viewport; it lies about
  area-light energy ratios.
- Don't raise samples to "be safe" on CPU — raise the test render's resolution
  instead; 48 + OIDN is the proven setting for stills.
