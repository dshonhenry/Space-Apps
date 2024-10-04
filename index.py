# import astropy.units as u
# from astropy.coordinates import SkyCoord
# from astroquery.gaia import Gaia
# import pandas
# Gaia.ROW_LIMIT = 20
# coord = SkyCoord(ra=280, dec=20, unit=(u.degree, u.degree), frame='icrs')
# query = """SELECT *, DISTANCE(81.28, -69.78, ra, dec) AS ang_sep
# FROM gaiadr3.gaia_source
# WHERE DISTANCE(81.28, -69.78, ra, dec) < 5./60.
# AND phot_g_mean_mag < 20.5
# AND parallax IS NOT NULL
# ORDER BY ang_sep ASC"""
# # Gaia.cone_search(coord, radius=u.Quantity(1.0, u.deg))
# results = Gaia.launch_job(query=query).get_results() #query.get_results()
# results.pprint()
# results = results.to_pandas()
# print(u.Quantity(1.0, u.deg))

import requests
import json
res = requests.get("https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+*+from+stellarhosts+where+sy_dist<10&format=json")
response = json.loads(res.text)
print(response)