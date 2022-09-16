from rdflib import Literal

from galacteek.core.models.sparql.tags import TagsSparQLModel
from galacteek.core.models.sparql.hashmarks import LDHashmarksSparQLListModel


class ProntoServiceModels:
    async def initializeSparQLModels(self):
        # All tags
        self.allTagsModel = TagsSparQLModel(
            graphUri='urn:ipg:i:love:itags',
            bindings={'tagNameRegex': Literal('')}
        )
        self.allTagsModel.update()

        self.allHashmarksModel = LDHashmarksSparQLListModel(
            graphUri='urn:ipg:i:love:hashmarks',
            rq='HashmarksSearch',
            bindings={'titleSearch': Literal('')}
        )
        self.allHashmarksModel.update()
