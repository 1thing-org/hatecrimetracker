from firestore.incidents import (insertIncident)
from google.cloud import translate

translate_api_client = translate.TranslationServiceClient()
LOCATION = "global"
PROJECT_ID='hate-crime-tracker'
PARENT = f"projects/{PROJECT_ID}/locations/{LOCATION}"
BATCH_SIZE=10

def translate_batch(batch, target_lang):
    if len(batch) == 0:
        return
    translated_batch = []
    for incident in batch:
        translated_batch.append(incident['title'])
        translated_batch.append(incident['abstract'])
    response = translate_api_client.translate_text(
            parent = PARENT,
            contents = translated_batch,
            mime_type = 'text/plain',  # mime types: text/plain, text/html
            source_language_code = 'en-US',
            target_language_code = target_lang
    )
    if len(response.translations) != len(translated_batch):
        raise SystemError('Translation result count {0} does not match original {1}'
            .format(len(response.translations, len(translated_batch))))

    for i in range(len(batch)):
        if batch[i].get('abstract_translate') is None:
            batch[i]['abstract_translate'] = {}
        if batch[i].get('title_translate') is None:
            batch[i]['title_translate'] = {}

        batch[i]['title_translate'].update({
            target_lang: response.translations[i*2].translated_text
        })
        batch[i]['abstract_translate'].update({
            target_lang: response.translations[i*2+1].translated_text
        })
    return batch

def save_batch(batch):
    for incident in batch:
        insertIncident(incident)

#translate and save batch of incidents if the given language does not exist
def translate_incidents(incidents, target_lang):
    batch = []
    for incident in incidents:
        # check if the target language exists
        if incident.get('title_translate', None) and incident.get('title_translate', {}).get(target_lang) is not None:
            continue
        batch.append(incident)
        if len(batch) >= BATCH_SIZE:
            batch = translate_batch(batch, target_lang)
            save_batch(batch)
            batch = []
    if len(batch) > 0:
        batch = translate_batch(batch, target_lang)
        save_batch(batch)
    return incidents #when translate batchs, incidents in incidents should be updated too

