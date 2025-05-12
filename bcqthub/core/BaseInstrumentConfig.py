from pydantic import BaseModel, Extra


# implements Pydantic's BaseModel so we can enforce a uniform config object between all drivers
# doing this without pydantic would be annoying because then we'd have to implement our own
# error checking and input validation and other crap..
class InstrumentConfig(BaseModel):

    """pydantic uses an inner 'config' class, which is essentially
    settings for how Pydantic should build and treat this model.
    """
    class Config:
        extra = Extra.allow  # allow arguments besides the ones we declare
        frozen = False       # frozen = True means that values cannot changex