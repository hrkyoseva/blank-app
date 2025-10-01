import os
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import io

# -------- SETTINGS --------
ROOT_DIR = "/workspaces/blank-app/"  # change to your folder root


# -------- HELPER FUNCTIONS --------
def collect_images(root_dir, use_raw):
    """
    Crawl folder structure and extract parameters into DataFrame.
    Filters based on whether raw_data is included.
    """
    records = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if not f.lower().endswith(".png"):
                continue

            is_raw = "raw_data" in f
            if use_raw and not is_raw:
                continue
            if not use_raw and is_raw:
                continue

            filepath = os.path.join(dirpath, f)
            rel_parts = os.path.relpath(filepath, root_dir).split(os.sep)

            try:
                # {d}um_{angle}/{sub}_{mode}/{plane}-plane/{wl}nm/{cross}_{pol}/{Ecomp}_{type}[_raw_data].png
                d, angle = rel_parts[0].split("um_")
                sub, mode = rel_parts[1].split("_")
                plane = rel_parts[2].replace("-plane", "")
                wl = rel_parts[3].replace("nm", "")
                cross, pol = rel_parts[4].split("_")

                # filename part: E_x_initial.png  or E_x_initial_raw_data.png
                fname_noext = f.replace(".png", "")
                parts = fname_noext.split("_")
                Ecomp = "_".join(parts[:2])  # first two parts = E_x, norm_E
                etype = parts[2]             # third part = initial/scattered/total

                records.append({
                    "diameter": d,
                    "angle": angle,
                    "substrate": sub,
                    "mode": mode,
                    "plane": plane,
                    "wavelength": wl,
                    "cross": cross,
                    "polarization": pol,
                    "E component": Ecomp,
                    "E type": etype,
                    "path": filepath
                })
            except Exception as e:
                print(f"Skipping {filepath} due to parse error: {e}")
    return pd.DataFrame(records)


def filter_dataframe(df, fixed_params):
    """Return filtered df given selected fixed parameter values"""
    fdf = df.copy()
    for k, v in fixed_params.items():
        if isinstance(v, list):
            fdf = fdf[fdf[k].isin(v)]
        elif v is not None:
            fdf = fdf[fdf[k] == v]
    return fdf


def parameter_selector(df, exclude=None, multi=False, key_prefix=""):
    """
    Compact parameter selector UI using expanders arranged in 4 columns.
    exclude = parameters to skip
    multi = if True -> multiselect, else -> radio
    """
    exclude = exclude or []
    params = [c for c in df.columns if c not in ["path"] + exclude]

    fixed_params = {}
    cols = st.columns(4)
    for i, p in enumerate(params):
        with cols[i % 4].expander(p, expanded=False):
            values = sorted(df[p].unique())
            if multi:
                selected = st.multiselect(f"{p} values", values, default=values, key=f"{key_prefix}{p}_multi")
            else:
                selected = st.radio(f"{p} value", values, index=0, key=f"{key_prefix}{p}_radio")
            fixed_params[p] = selected
    return fixed_params

# def make_grid_image(grid, row_labels, col_labels, shared_text):
#     """Stitch grid of images into one exportable PNG."""
#     if not grid:
#         return None

#     # Load PIL images
#     pil_grid = [[Image.open(path) if path else None for path in row] for row in grid]

#     # Get max sizes
#     max_w = max(img.width for row in pil_grid for img in row if img)
#     max_h = max(img.height for row in pil_grid for img in row if img)

#     rows, cols = len(pil_grid), len(pil_grid[0])
#     margin = 40

#     # Create canvas with extra space for labels
#     canvas_w = cols * (max_w + margin) + margin
#     canvas_h = rows * (max_h + margin) + margin + 100
#     canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
#     draw = ImageDraw.Draw(canvas)

#     # Fonts (fallback to default if no truetype available)
#     try:
#         font = ImageFont.truetype("arial.ttf", 20)
#     except:
#         font = ImageFont.load_default()

#     # Draw shared text at top
#     draw.text((margin, 10), shared_text, fill="black", font=font)

#     # Place images + labels
#     for r in range(rows):
#         y = 100 + r * (max_h + margin)
#         draw.text((5, y + max_h // 2), row_labels[r], fill="black", font=font)
#         for c in range(cols):
#             x = margin + c * (max_w + margin)
#             if pil_grid[r][c]:
#                 img = pil_grid[r][c]
#                 canvas.paste(img, (x, y))
#             if r == 0:
#                 draw.text((x + max_w // 2, 70), col_labels[c], fill="black", font=font)

#     return canvas

def make_grid_image(image_paths, row_labels=None, col_labels=None):
    """Stitch a list of lists of images into one grid PNG"""
    if not image_paths:
        return None

    rows = len(image_paths)
    cols = len(image_paths[0]) if rows > 0 else 0

    imgs = [[Image.open(p) for p in row] for row in image_paths]

    w = max(im.size[0] for row in imgs for im in row)
    h = max(im.size[1] for row in imgs for im in row)

    grid_img = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    draw = ImageDraw.Draw(grid_img)

    for i, row in enumerate(imgs):
        for j, im in enumerate(row):
            grid_img.paste(im.resize((w, h)), (j * w, i * h))

    return grid_img

# -------- STREAMLIT APP --------
st.set_page_config(layout="wide")
st.title("Simulation Image Browser")

raw_choice = st.radio("Select image version", ["with raw_data", "without raw_data"])
use_raw = raw_choice == "with raw_data"

df = collect_images(ROOT_DIR, use_raw)
if df.empty:
    st.warning("No images found after filtering.")
    st.stop()

mode = st.radio("Choose mode:", ["2-parameter comparison", "Free grid"])

params = [c for c in df.columns if c not in ["path"]]

if mode == "2-parameter comparison":
    row_col = st.columns(2)
    with row_col[0].expander("Row parameter"):
        row_param = st.radio("Select row parameter", params, key="row_param")
        row_values = st.multiselect(f"{row_param} values", sorted(df[row_param].unique()), key="row_vals")
    with row_col[1].expander("Column parameter"):
        col_param = st.radio("Select column parameter", params, key="col_param")
        col_values = st.multiselect(f"{col_param} values", sorted(df[col_param].unique()), key="col_vals")

    st.subheader("Shared Parameters (fixed for all images)")
    fixed_params = parameter_selector(df, exclude=[row_param, col_param], multi=False, key_prefix="shared_")

    filtered = filter_dataframe(df, fixed_params)

    if row_values and col_values:
        st.markdown("### Shared Parameters")
        st.write(", ".join([f"{k}={v}" for k, v in fixed_params.items()]))

        # Build grid
        grid_paths = []
        header_cols = st.columns(len(col_values) + 1)
        header_cols[0].write("")
        for ci, cv in enumerate(col_values):
            header_cols[ci + 1].write(f"**{cv}**")

        for rv in row_values:
            row_cols = st.columns(len(col_values) + 1)
            row_cols[0].write(f"**{rv}**")
            row_paths = []
            for ci, cv in enumerate(col_values):
                match = filtered[(filtered[row_param] == rv) & (filtered[col_param] == cv)]
                if not match.empty:
                    img_path = match.iloc[0]["path"]
                    row_cols[ci + 1].image(Image.open(img_path),  width='stretch')
                    row_paths.append(img_path)
                else:
                    row_cols[ci + 1].write("No image")
                    row_paths.append(None)
            grid_paths.append(row_paths)

        # Export button
        if any(any(r) for r in grid_paths):
            img_grid = make_grid_image([[p for p in row if p] for row in grid_paths])
            if img_grid:
                buf = io.BytesIO()
                img_grid.save(buf, format="PNG")
                st.download_button("Download grid as PNG", buf.getvalue(), "comparison_grid.png", "image/png")

elif mode == "Free grid":
    grid_rows = st.number_input("Number of rows", min_value=1, max_value=6, value=2)
    grid_cols = st.number_input("Number of columns", min_value=1, max_value=6, value=2)

    st.subheader("Parameter selection for each cell")
    cell_filters = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            st.markdown(f"<a name='cell{r}_{c}'></a>", unsafe_allow_html=True)
            st.markdown(f"**Cell ({r+1},{c+1})**")
            filters = parameter_selector(df, key_prefix=f"cell{r}_{c}_")
            cell_filters.append(((r, c), filters))

    st.subheader("Image grid")
    grid_paths = []
    for r in range(grid_rows):
        row_cols = st.columns(grid_cols)
        row_paths = []
        for c in range(grid_cols):
            _, filters = cell_filters[r * grid_cols + c]
            match = filter_dataframe(df, filters)
            if not match.empty:
                img_path = match.iloc[0]["path"]
                row_cols[c].image(Image.open(img_path),  width='stretch',
                                  caption=f"[Edit params](#cell{r}_{c})")
                row_paths.append(img_path)
            else:
                row_cols[c].write("No match")
                row_paths.append(None)
        grid_paths.append(row_paths)

    if any(any(r) for r in grid_paths):
        img_grid = make_grid_image([[p for p in row if p] for row in grid_paths])
        if img_grid:
            buf = io.BytesIO()
            img_grid.save(buf, format="PNG")
            st.download_button("Download grid as PNG", buf.getvalue(), "free_grid.png", "image/png")