from cultverify import CulturalVerifier
from cultverify.targets import response_spans
from conftest import FixtureLLM, PROMPT


def test_response_spans_preserve_exact_markdown_and_punctuation():
    response = 'Offer **alternatives** such as e.g., "Zitrone".\nRespect their decision.'
    spans = response_spans(response)
    assert spans
    assert all(span["text"] in response for span in spans)
    assert any('e.g., "Zitrone"' in span["text"] for span in spans)
    assert any("**alternatives**" in span["text"] for span in spans)


def test_target_extractor_selects_span_id_and_python_restores_exact_quote(setup):
    config, _, retriever, _ = setup
    response = 'Offer **alternatives** such as e.g., "Zitrone". Respect their decision.'

    def target(payload):
        selected = next(span for span in payload["response_spans"] if 'e.g., "Zitrone"' in span["text"])
        return {
            "targets": [
                {
                    "span_id": selected["span_id"],
                    "epistemic_type": "context_dependent_recommendation",
                    "dimension_ids": ["D03"],
                }
            ]
        }

    llm = FixtureLLM(config, overrides={"target_extractor_v1": target})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, response)

    assert result.status == "completed"
    assert result.targets[0].response_quote == 'Offer **alternatives** such as e.g., "Zitrone".'
    target_call = next(call for call in llm.calls if call["stage"] == "target_extractor_v1")
    assert "response" not in target_call["payload"]
    assert "response_spans" in target_call["payload"]
    assert "response_quote" not in target_call["schema"]["$defs"]["TargetSelectionDraft"]["properties"]


def test_dimension_scorer_does_not_generate_response_quotes(setup):
    config, _, retriever, _ = setup
    llm = FixtureLLM(config)
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(
        PROMPT, "Respect the published arrangements."
    )

    assert result.status == "completed"
    scorer_call = next(call for call in llm.calls if call["stage"] == "dimension_scorer_v1")
    schema_text = str(scorer_call["schema"])
    assert "response_quotes" not in schema_text
    assert result.dimension_scores[0].response_quotes == (result.targets[0].response_quote,)
