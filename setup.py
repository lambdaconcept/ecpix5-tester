from setuptools import setup, find_packages


def scm_version():
    def local_scheme(version):
        if version.tag and not version.distance:
            return version.format_with("")
        else:
            return version.format_choice("+{node}", "+{node}.dirty")
    return {
        "relative_to": __file__,
        "version_scheme": "guess-next-dev",
        "local_scheme": local_scheme
    }


setup(
    name="ecpix5_tester",
    use_scm_version=scm_version(),
    author="LambdaConcept",
    author_email="contact@lambdaconcept.com",
    #description="",
    #long_description="""TODO""",
    setup_requires=["setuptools_scm"],
    install_requires=[
        "nmigen>=0.1,<0.5",
        "nmigen-boards",
    ],
    entry_points={
        "console_scripts": [
        ]
    },
    extras_require={
    },
    packages=find_packages(),
)
