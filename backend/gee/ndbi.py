"""NDBI (Normalized Difference Built-up Index) helper — used by UHI module."""
import ee


def ndbi_image_and_aoi(district_name: str, start_date: str, end_date: str):
    """Build a median NDBI image from Landsat 9 SR and return (ndbi_image, aoi)."""
    rwanda = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Rwanda"),
            ee.Filter.eq("ADM2_NAME", district_name),
        )
    )
    aoi = rwanda.geometry()

    def apply_scale_factors(image):
        optical = image.select("SR_B.").multiply(0.0000275).add(-0.2)
        return image.addBands(optical, None, True)

    def compute_ndbi(image):
        # NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)  →  Landsat9: SR_B6 / SR_B5
        ndbi = image.normalizedDifference(["SR_B6", "SR_B5"]).rename("NDBI")
        return ndbi.copyProperties(image, ["system:time_start"])

    collection = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUD_COVER", 20))
        .map(apply_scale_factors)
        .map(compute_ndbi)
    )
    ndbi_median = collection.median().clip(aoi)
    return ndbi_median, aoi
