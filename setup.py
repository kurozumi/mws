from distutils.core import setup

if __name__ == "__main__":
    setup(
        name="mws",
        version="1.0",
        description="wrapper for MWS",
        packages=["mws"],
        install_requires=[
            "cchardet",
            "PySocks"
        ]
    )
