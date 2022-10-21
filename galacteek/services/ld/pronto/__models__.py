from rdflib import Literal

from galacteek.config.cmods import app as config_app
from galacteek.core.models.sparql.hashmarks import LDHashmarksSparQLListModel
from galacteek.core.models.sparql.hashmarks import LDHashmarksItemModel
from galacteek.core.models.sparql.tags import TagsSparQLModel
from galacteek.core.models.sparql.tags import TagsPreferencesModel


class ProntoServiceModels:
    async def initializeSparQLModels(self):
        langTag = config_app.defaultContentLangTag()

        # All tags
        self.allTagsModel = TagsSparQLModel(
            graphUri='urn:ipg:i:love:itags',
            bindings={
                'langTag': Literal(langTag),
                'tagNameRegex': Literal('')
            }
        )
        self.allTagsModel.update()

        self.tagsPrefsModel = TagsPreferencesModel(
            graphUri='urn:ipg:i:love:itags'
        )
        self.tagsPrefsModel.update()

        if 0:
            self.allHashmarksModel = LDHashmarksSparQLListModel(
                graphUri='urn:ipg:i:love:hashmarks',
                rq='HashmarksSearch',
                bindings={'searchQuery': Literal('')}
            )

        # Hashmarks item model
        self.allHashmarksItemModel = LDHashmarksItemModel(
            graphUri='urn:ipg:i:love:hashmarks',
            rq='HashmarksSearchGroup',
            columns=['Title'],
            bindings={
                'searchQuery': Literal(''),
                'mimeCategoryQuery': Literal(''),
                'langTagMatch': Literal('en')  # BC
            }
        )
        self.allHashmarksItemModel.update()

        await self.psPublish({
            'type': 'ProntoModelsReady'
        })
