import math
from astroquery.gaia import Gaia
import astropy.units as u
from astropy.coordinates import SkyCoord
import requests
import json
# tables = Gaia.load_tables(only_names=True)
# for table in tables:
#     print(table)
#     print()


from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "https://dshonhenry.github.io/space-apps-ui"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins. You can restrict to specific domains.
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

def degreesToRads(deg):
    return deg * (math.pi/180)

def to_ui_data(stars, distance_column,  name_column="DESIGNATION", ra_column="ra", dec_column="dec"):
    output = []
    for star in stars:
        output.append(dict(
            x = (star[distance_column]) * math.cos(degreesToRads(star[dec_column])) * math.sin(degreesToRads(star[ra_column])), 
            y = (star[distance_column]) * math.sin(degreesToRads(star[dec_column])),
            z = (star[distance_column]) * math.cos(degreesToRads(star[dec_column])) * math.cos(degreesToRads(star[ra_column])),
            name = star[name_column]
        ))
    return output


@app.get("/")
def read_root():
    tables = Gaia.load_tables(only_names=True)
    return tables

@app.get("/earthStars")
def read_stars():
    Gaia.MAIN_GAIA_TABLE = "gaiadr3.gaia_source"
    Gaia.ROW_LIMIT = 5
    coord = SkyCoord(ra=0, dec=0, unit=(u.degree, u.degree), frame='icrs')
    width = u.Quantity(30, u.deg)
    height = u.Quantity(30, u.deg)
    query = Gaia.query_object(coordinate=coord, width=width, height=height)
    # result = query.to_pandas().to_json(orient='records')
    query = """SELECT Top 3000 ra, dec, DESIGNATION, distance_gspphot
    FROM gaiadr3.gaia_source
    WHERE distance_gspphot IS NOT NULL
    AND distance_gspphot < 200"""
    result = Gaia.launch_job(query=query).get_results().to_pandas().to_json(orient='records') #query.get_results()
    stars = to_ui_data(json.loads(result), "distance_gspphot")
    return stars
    #return Response(content = result, media_type="application/json")

@app.get("/hostStars")
def read_host_stars():
    res = requests.get("https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+TOP+1500+*+from+stellarhosts+where+sy_dist<1000+order+by+sy_dist&format=json")
    response = json.loads(res.text)
    stars = to_ui_data(response, "sy_dist", "hostname")    
    return stars

@app.get("/starsNear")
def read_stars_near(ra, dec, dist):
    num_results = 10000
    max_distance_factor = 1
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

    # set max_distance_factor = 0.8 or some number < 1 will reduce the number of results but will make the query faster, use this to tweak the number of results to your liking
    max_distance *= max_distance_factor

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
        SELECT TOP 100000 ra, dec, distance_gspphot, designation,
            SQRT({dist_squared} + POWER(distance_gspphot, 2) - {factor} * distance_gspphot * COS((DISTANCE({ra}, {dec}, ra, dec) * PI()) / 180)) AS dist_from_center
        FROM gaiadr3.gaia_source
        WHERE distance_gspphot > {near_limit}
            AND distance_gspphot < {far_limit}
            AND ra BETWEEN {ra_min} AND {ra_max}
            AND dec BETWEEN {dec_min} AND {dec_max}
    ) AS subquery
    WHERE dist_from_center < {max_distance}
    ORDER BY dist_from_center ASC
    """
    result = Gaia.launch_job(query=query).get_results().to_pandas().to_json(orient="records")
    stars = to_ui_data(json.loads(result), "distance_gspphot", "designation")
    return stars
    

    # return Response(content=stars, media_type="application/json")

@app.get("/planets")
def read_planets():
    res = requests.get("https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+sy_dist,ra,dec,pl_name+from+pscomppars+where+sy_dist<1000+and+sy_dist>320+order+by+sy_dist&format=json")
    # planets = json.loads(res)
    # output = []
    # for planet in planets:
    #     output.append(dict(
    #         x = planet["sy_dist"] * math.cos(degreesToRads(planet["dec"])) * math.sin(degreesToRads(planet["ra"])), 
    #         y = planet["sy_dist"]* math.sin(degreesToRads(planet["dec"])),
    #         z = planet["sy_dist"]* math.cos(degreesToRads(planet["dec"])) * math.cos(degreesToRads(planet["ra"])),
    #         name = planet["name"]
    #         ra = planet["ra"]
    #         dec = planet["dec"]

    #     ))
    # return output
    return Response(content = res.content, media_type=res.headers["Content-Type"])
    
