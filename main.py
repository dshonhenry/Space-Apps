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
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def degreesToRads(deg):
    return deg * (math.pi/180)

def to_ui_data(stars, distance_column,  name_column="DESIGNATION", ra_column="ra", dec_column="dec"):
    output = []
    for star in stars:
        output.append(dict(
            z = (star[distance_column]) * math.cos(degreesToRads(star[dec_column])) * math.cos(degreesToRads(star[ra_column])),
            x = (star[distance_column]) * math.cos(degreesToRads(star[dec_column])) * math.sin(degreesToRads(star[ra_column])), 
            y = (star[distance_column]) * math.sin(degreesToRads(star[dec_column])),
            name = star[name_column]
        ))
    return output


@app.get("/")
def read_root():
    tables = Gaia.load_tables(only_names=True)
    return tables

@app.get("/stars")
def read_stars():
    Gaia.MAIN_GAIA_TABLE = "gaiadr3.gaia_source"
    Gaia.ROW_LIMIT = 5
    coord = SkyCoord(ra=0, dec=0, unit=(u.degree, u.degree), frame='icrs')
    width = u.Quantity(30, u.deg)
    height = u.Quantity(30, u.deg)
    query = Gaia.query_object(coordinate=coord, width=width, height=height)
    # result = query.to_pandas().to_json(orient='records')
    query = """SELECT ra, dec, DESIGNATION, distance_gspphot
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
    dist = float(dist)
    ra = float(ra)
    dec = float(dec)

    max_distance = 100

    near_limit = dist - max_distance
    far_limit = dist + max_distance

    radius = math.degrees(math.atan(max_distance/near_limit))
    print(radius)

    query = f"""SELECT TOP 200 ra, dec, distance_gspphot, SQRT(POWER({dist},2) + POWER(distance_gspphot, 2) - 2*{dist}*distance_gspphot*COS((DISTANCE({ra}, {dec}, ra, dec)*PI())/180))  AS dist_from_center
                FROM gaiadr3.gaia_source
                WHERE distance_gspphot > {near_limit}
                AND distance_gspphot < {far_limit}
                AND contains(point(ra, dec), circle({ra}, {dec}, 3  )) = 1
                AND SQRT(POWER({dist},2) + POWER(distance_gspphot, 2) - 2*{dist}*distance_gspphot*COS((DISTANCE({ra}, {dec}, ra, dec)*PI())/180)) < {max_distance}
                ORDER BY dist_from_center ASC
            """
    
    # if(near_limit < 0):
    #     op_ra = ra + 180
    #     op_dec = dec * - 1
    result = Gaia.launch_job(query=query).get_results().to_pandas().to_json(orient='records') #query.get_results()
    return Response(content = result, media_type="application/json")

@app.get("/test")
def test():
    # 
    dist = 396.3320
    ra = 294.635917
    dec = 46.0664076
    query = f"""SELECT TOP 5 distance_gspphot, SQRT(POWER({dist},2) + POWER(distance_gspphot, 2) - 2*{dist}*distance_gspphot*COS((DISTANCE({ra}, {dec}, ra, dec)*PI())/180))  AS dist_from_center
                FROM gaiadr3.gaia_source
                WHERE distance_gspphot is not null
                AND SQRT(POWER({dist},2) + POWER(distance_gspphot, 2) - 2*{dist}*distance_gspphot*COS((DISTANCE({ra}, {dec}, ra, dec)*PI())/180)) < 10
                AND phot_g_mean_mag < 20.5
                """
    result = Gaia.launch_job(query=query).get_results().to_pandas().to_json(orient='records') #query.get_results()
    return Response(content = result, media_type="application/json")
    