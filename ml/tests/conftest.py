import pytest
from PIL import Image


@pytest.fixture()
def toy_images_root(tmp_path):
    """Tiny synthetic image tree with Mendeley-style class folders + edge cases."""
    root = tmp_path / "raw" / "extracted" / "plantvillage without augmentation"
    classes = {
        "Tomato_early_blight": 12,
        "Potato___Early_blight": 8,  # spMohanty-style name, must normalize identically
        "Background_without_leaves": 3,  # explicitly excluded
        "Bell_pepper leaf": 4,  # real PlantVillage class, out of V1 scope -> recorded as unmapped
    }
    for cls, count in classes.items():
        folder = root / cls
        folder.mkdir(parents=True)
        for i in range(count):
            Image.new("RGB", (12, 12), (i * 19 % 255, 80, 40)).save(folder / f"{cls}_{i}.jpg")
    return root


@pytest.fixture()
def toy_zip(tmp_path):
    """Outer zip containing a nested *without_augmentation* zip (mimics 'Download All')."""
    import zipfile

    inner_dir = tmp_path / "inner"
    cls_dir = inner_dir / "dataset without augmentation" / "Tomato_early_blight"
    cls_dir.mkdir(parents=True)
    for i in range(4):
        Image.new("RGB", (8, 8), (200, i * 30, 10)).save(cls_dir / f"t_{i}.jpg")
    other = inner_dir / "dataset without augmentation" / "Apple_healthy"
    other.mkdir(parents=True)
    Image.new("RGB", (8, 8), (0, 200, 0)).save(other / "a_0.jpg")

    inner_zip_path = tmp_path / "plant_leaf_diseases_dataset_without_augmentation.zip"
    with zipfile.ZipFile(inner_zip_path, "w") as zf:
        for p in inner_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(inner_dir))

    outer_zip_path = tmp_path / "download_all.zip"
    with zipfile.ZipFile(outer_zip_path, "w") as zf:
        zf.write(inner_zip_path, inner_zip_path.name)
    return outer_zip_path


@pytest.fixture()
def toy_plantdoc_zip(tmp_path):
    """Flat zip using real PlantDoc class-folder names (GitHub-zip style)."""
    import zipfile

    staging = tmp_path / "pd_staging"
    for cls, count in {"Tomato Early blight leaf": 3, "Apple leaf": 2}.items():
        cls_dir = staging / cls
        cls_dir.mkdir(parents=True)
        for i in range(count):
            Image.new("RGB", (8, 8), (50, i * 40, 90)).save(cls_dir / f"p_{i}.jpg")
    zip_path = tmp_path / "plantdoc.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in staging.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(staging))
    return zip_path
