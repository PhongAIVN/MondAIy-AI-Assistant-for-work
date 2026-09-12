from src.agents.pipeline.nodes.make_batches import make_batches_node


def test_make_batches_is_bounded_and_tags_items(pipeline_state):
    pipeline_state["filtered"] = [{"id": f"m{i}"} for i in range(7)]

    result = make_batches_node(pipeline_state)

    assert [len(batch) for batch in result["batches"]] == [6, 1]
    assert all("_pipeline_batch_id" in item for item in pipeline_state["filtered"])
