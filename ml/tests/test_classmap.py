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
