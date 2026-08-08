from pathlib import Path

from ml.data import classmap

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


def test_mendeley_style_names_map():
    assert classmap.map_class_dir("plantvillage", "Tomato_early_blight") == "tomato_early_blight"
    assert classmap.map_class_dir("plantvillage", "Corn_gray_leaf_spot") == "corn_cercospora_gray_leaf_spot"


def test_spmohanty_style_names_map():
    assert classmap.map_class_dir("plantvillage", "Apple___Apple_scab") == "apple_scab"
    assert classmap.map_class_dir("plantvillage", "Potato___healthy") == "potato_healthy"
    assert (
        classmap.map_class_dir("plantvillage", "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot")
        == "corn_cercospora_gray_leaf_spot"
    )
    assert (
        classmap.map_class_dir("plantvillage", "Tomato_Spider_mites_Two_spotted_spider_mite")
        == "tomato_spider_mites"
    )


# The 21 in-scope class folders of the WITHOUT-augmentation archive — verbatim dirnames as
# observed in the real 2026-08-08 import report (trailing-underscore variants normalize
# identically, as they use the same `Crop___Condition` convention). This is the evidence
# list for full V1-scope coverage: aliases are added from observed names only, never guessed.
WITHOUT_AUG_DIRNAMES = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Corn___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn___Common_rust_",
    "Corn___Northern_Leaf_Blight",
    "Corn___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]


def test_without_augmentation_variant_names_map():
    assert classmap.map_class_dir("plantvillage", "Corn___Cercospora_leaf_spot Gray_leaf_spot") == (
        "corn_cercospora_gray_leaf_spot"
    )
    assert classmap.map_class_dir("plantvillage", "Tomato___Spider_mites Two-spotted_spider_mite") == (
        "tomato_spider_mites"
    )
    assert classmap.map_class_dir("plantvillage", "Tomato___Tomato_Yellow_Leaf_Curl_Virus") == (
        "tomato_yellow_leaf_curl_virus"
    )
    assert classmap.map_class_dir("plantvillage", "Tomato___Tomato_mosaic_virus") == "tomato_mosaic_virus"


def test_real_extraction_folder_list_covers_full_v1_scope():
    """All 21 documented disease_ids are reachable from the real extraction's dirnames."""
    covered = {classmap.map_class_dir("plantvillage", name) for name in WITHOUT_AUG_DIRNAMES}
    assert None not in covered
    expected = {t for t in classmap.PLANTVILLAGE_MAP.values() if t is not classmap.EXCLUDE}
    assert covered == expected  # exactly the 21 documented classes — full V1 scope


def test_background_is_explicitly_excluded():
    assert classmap.map_class_dir("plantvillage", "Background_without_leaves") is classmap.EXCLUDE


def test_out_of_scope_classes_are_unmapped_not_mapped():
    assert classmap.map_class_dir("plantvillage", "Bell_pepper leaf") is None
    assert classmap.map_class_dir("plantdoc", "Blueberry leaf") is None


def test_plantdoc_field_names_map():
    assert classmap.map_class_dir("plantdoc", "Tomato two spotted spider mites leaf") == "tomato_spider_mites"
    assert classmap.map_class_dir("plantdoc", "Potato leaf late blight") == "potato_late_blight"


def test_every_mapping_target_exists_in_taxonomy():
    problems = classmap.validate_against_taxonomy(CONFIG_DIR)
    assert problems == []
