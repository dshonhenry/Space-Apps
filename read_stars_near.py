import json
import math
import random
import time

from astroquery.gaia import Gaia
from fastapi import Response


def read_stars_near(ra, dec, dist, num_results=10000):
    dist = float(dist)
    ra = float(ra)
    dec = float(dec)

    # the formula for max_distance seems very random, but it's based on the following:
    # - there is a burgeoning of stars from around 40 to 1000 parsecs, so we want to reduce the max_distance in that range
    # - there should be about 100-5000 results for distances < 2000 parsecs (depends on direction, there is a lot of variation based on direction)
    # - probably a good idea set upper limit of dist to 3000-5000 parsecs.
    if dist <= 40:
        max_distance = 40
    elif dist > 40 and dist <= 440:
        max_distance = 40 - (dist - 40) ** 0.5
    else:
        max_distance = 20 + (dist - 440) ** 0.5

    near_limit = max(dist - max_distance, 1e-12)
    far_limit = dist + max_distance

    radius = max(0, math.degrees(math.atan(max_distance / near_limit)))

    ra_min = ra - radius
    ra_max = ra + radius
    dec_min = dec - radius
    dec_max = dec + radius

    dist_squared = dist**2
    factor = 2 * dist

    print("\nra:", ra, "dec:", dec, "dist:", dist, "max_distance:", max_distance, "radius:", radius)

    # The query is optimized in the following ways:
    # - the operation contains(point(ra, dec), circle({ra}, {dec}, 3  )) = 1 is rather expensive, so we use a rectangular region (ra_min, ra_max, dec_min, dec_max) instead of a circular region
    # - we use a subquery to calculate the distance from the center star, so that:
    #   + first, we don't have to calculate it twice like in the original query
    #   + second, the calculation is only done for the stars that pass the distance and rectangular region filters
    #   + third, the result limit of the subquery is set to 100,000, which is logically incorrect, but is a workaround so that the query doesn't time-out for particularly crowded regions
    # - all the values that are not row-dependent are now stored in variables, so that they are only calculated once: dist_squared, factor, ra_min, ra_max, dec_min, dec_max...
    # The query is not time-out anymore, but may take up to 20-30 seconds for particularly crowded regions.
    query = f"""
    SELECT TOP {num_results} * FROM (
        SELECT TOP 100000 ra, dec, distance_gspphot,
            SQRT({dist_squared} + POWER(distance_gspphot, 2) - {factor} * distance_gspphot * COS((DISTANCE({ra}, {dec}, ra, dec) * PI()) / 180)) AS dist_from_center
        FROM gaiadr3.gaia_source_lite
        WHERE distance_gspphot > {near_limit}
            AND distance_gspphot < {far_limit}
            AND ra BETWEEN {ra_min} AND {ra_max}
            AND dec BETWEEN {dec_min} AND {dec_max}
    ) AS subquery
    WHERE dist_from_center < {max_distance}
    ORDER BY dist_from_center ASC
    """

    start_time = time.time()
    result = Gaia.launch_job(query=query).get_results().to_pandas().to_json(orient="records")
    print(f"Time taken: {time.time() - start_time:.2f} seconds")

    result_json = json.loads(result)
    print("result length:", len(result_json))

    with open("result.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(result_json, indent=4))

    return Response(content=result, media_type="application/json")


if __name__ == "__main__":
    distances = [0, 10, 100, 200, 500, 750, 1000, 2000, 3000, 5000, 10000]
    for dist in distances:
        read_stars_near(random.uniform(0, 360), random.uniform(-90, 90), dist)
