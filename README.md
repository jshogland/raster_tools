# raster_tools
RMRS Raster Utility Project

## Dependencies
* [cython](https://cython.readthedocs.io/en/latest/)
* [dask](https://dask.org/)
* [dask_image](https://image.dask.org/en/latest/)
* [dask-geopandas](https://github.com/geopandas/dask-geopandas)
* [geopandas](https://geopandas.org/en/stable/)
* [numba](https://numba.pydata.org/)
* [rasterio](https://rasterio.readthedocs.io/en/latest/)
* [rioxarray](https://corteva.github.io/rioxarray/stable/)
* [xarray](https://xarray.pydata.org/en/stable/)
* [cupy](https://cupy.dev/): optional and very experimental

## Contributing
1. Fork the _raster_tools_ repo.
2. Clone your fork.
3. Move to the _raster_tools_ project root:

    ```sh
    $ cd raster_tools
    ```

4. Create a python virtual environment

    With conda:

    ```sh
    $ conda env create -f requirements/dev.yml
    $ conda activate rstools
    ```

    With python:

    ```sh
    $ python -m venv venv
    $ . venv/bin/activate
    $ pip install -r ./requirements/dev.txt
    ```

5. Install the project into the virtual environment and build the cython modules:

    ```sh
    $ pip install --no-build-isolation -e .
    ```

6. Setup pre-commit hooks

    ```sh
    $ pre-commit install
    ```
7. Create your development branch:

    ```sh
    $ git checkout -b my-dev-branch
    ```

8. Make your changes. If you make any changes to the Cython code, you can
   rebuild with:

   ```sh
   python setup.py build_ext -i -f
   ```

9. Run the tests and fix anything that broke:

    ```sh
    $ nose2
    ```

10. (Optional) Run `pre-commit` to find/fix any formatting and flake8 issues:

    ```sh
    $ pre-commit run --all-files
    ```

    This will run `isort`, `black`, and `flake8` on the repo's files. It is
    recommended to do this and fix any errors that are flagged so that the
    changes can be cleanly commited.

11. Commit your changes to your branch and push to your remote repo:

    ```sh
    $ git add .
    $ git commit -m "A detailed description of the changes."
    $ git push origin my-dev-branch
    ```

12. Submit a pull request through GitHub.
