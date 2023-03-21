from rdflib import Literal

from galacteek.config.cmods import app as config_app
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
            graphUri='urn:ipg:i:love:itags',
            bindings={
                'langTagMatch': Literal(langTag)
            }
        )
        self.tagsPrefsModel.update()

        # Hashmarks item model
        self.allHashmarksItemModel = LDHashmarksItemModel(
            graphUri='urn:ipg:i:love:hashmarks',
            rq='HashmarksSearchGroup',
            columns=['Title'],
            bindings={
                'searchQuery': Literal(''),
                'mimeCategoryQuery': Literal(''),
                'langTagMatch': Literal(langTag)
            }
        )
        self.allHashmarksItemModel.update()

        await self.psPublish({
            'type': 'ProntoModelsReady'
        })
