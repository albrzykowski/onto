"""Mock fixtures for testing - used by BDD tests."""
from app.pipeline.llm_processor import LLMProcessor, LLMResponse


def extract_mock_entities_with_definitions(text: str) -> dict:
    """Extract entities with definitions for BDD tests."""
    words = text.split()
    entities = []
    relations = []
    entity_map = {}

    DEFINITIONS = {
        "Alice": "a person named Alice",
        "White Rabbit": "a rabbit character known as White Rabbit",
    }

    id_counter = 1
    i = 0
    while i < len(words):
        word = words[i]
        clean_word = word.strip(".,!?:;\"'")
        if clean_word and clean_word[0].isupper():
            entity_words = [clean_word]
            while i + 1 < len(words) and words[i + 1][0].isupper():
                i += 1
                entity_words.append(words[i].strip(".,!?:;\"'"))
            entity_label = " ".join(entity_words)
            if entity_label not in entity_map:
                entity_id = f"E{id_counter}"
                entity_map[entity_label] = entity_id
                definition = DEFINITIONS.get(entity_label, f"an entity identified as {entity_label}")
                entities.append({
                    "id": entity_id,
                    "label": entity_label,
                    "type": "Person",
                    "definition": definition,
                })
                id_counter += 1
        i += 1

    verbs = ["met", "works", "at", "leads", "acquired", "founded", "created", "owns"]
    i = 0
    while i < len(words):
        word = words[i]
        clean_word = word.strip(".,!?:;\"'")
        if clean_word.lower() in verbs:
            subj_word = None
            obj_word = None
            j = i - 1
            while j >= 0:
                w = words[j].strip(".,!?:;\"'")
                if w.lower() in ["the", "a", "an"]:
                    j -= 1
                    continue
                if w in entity_map:
                    subj_word = w
                elif j + 1 <= i and words[j + 1].lower() in ["the", "a", "an"]:
                    multi_word = []
                    k = j
                    while k <= i:
                        sw = words[k].strip(".,!?:;\"'")
                        if sw.lower() not in ["the", "a", "an"]:
                            multi_word.append(sw)
                        k += 1
                    potential = " ".join(multi_word)
                    if potential in entity_map:
                        subj_word = potential
                break
                j -= 1
            j = i + 1
            while j < len(words):
                w = words[j].strip(".,!?:;\"'")
                if w.lower() in ["the", "a", "an"]:
                    j += 1
                    continue
                if w in entity_map:
                    obj_word = w
                else:
                    multi_word = []
                    k = j
                    while k < len(words):
                        sw = words[k].strip(".,!?:;\"'")
                        if sw[0].isupper() if sw and len(sw) > 0 else False:
                            multi_word.append(sw)
                            k += 1
                        else:
                            break
                    if multi_word:
                        potential = " ".join(multi_word)
                        if potential in entity_map:
                            obj_word = potential
                        else:
                            obj_word = words[j].strip(".,!?:;\"'")
                break
                j += 1
            if subj_word and obj_word and subj_word in entity_map and obj_word in entity_map:
                relations.append({
                    "subject": entity_map[subj_word],
                    "predicate": clean_word.lower(),
                    "object": entity_map[obj_word],
                })
        i += 1

    return {"entities": entities, "relations": relations}


def mock_get_embedding(text: str) -> list[float]:
    """Mock embedding for testing. Returns unique vector based on text content."""
    import hashlib
    hash_bytes = hashlib.sha256(text.encode()).digest()
    vector = [b / 255.0 for b in hash_bytes]
    while len(vector) < 1536:
        vector.extend(vector[: min(32, len(vector))])
    return vector[:1536]


class MockLLMProcessor(LLMProcessor):
    """Mock LLM processor for BDD tests."""

    async def process(self, text: str) -> LLMResponse:
        if not text:
            return LLMResponse(content={}, success=False, error="Empty text")
        return LLMResponse(content=extract_mock_entities_with_definitions(text), success=True)
