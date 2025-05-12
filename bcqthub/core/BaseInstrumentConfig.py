# # from pydantic import BaseModel, Extra
from pydantic import BaseModel

# #   I'm testing Pydantic's BaseModel so we can enforce a uniform config object 
# # between all drivers.
# #   doing this without pydantic would be annoying because then we'd have to 
# # implement our own error checking and input validation...

class InstrumentConfig(BaseModel):
    pass

#     """
#         pydantic uses an inner 'config' class, which is essentially
#         settings for how Pydantic should build and treat this model.
#     """
#     class Config:
#         extra = Extra.allow  # allow arguments besides the ones we declare
#         frozen = False       # frozen = True means that values cannot changex
        
        
# class ExperimentConfig(BaseModel):

#     """
#         pydantic uses an inner 'config' class, which is essentially
#         settings for how Pydantic should build and treat this model.
#     """
#     class Config:
#         extra = Extra.allow  # allow arguments besides the ones we declare
#         frozen = False       # frozen = True means that values cannot changex