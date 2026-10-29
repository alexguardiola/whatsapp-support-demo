from support_bot.knowledge import load_chunks


def test_chunks_have_stable_ids_and_sources(chunks):
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
    assert "tarifas#sesion-de-fisioterapia-general" in ids
    assert all(c.text and c.title for c in chunks)


def test_disclaimer_blockquotes_are_not_chunks(chunks):
    assert not any("Negocio ficticio" in c.text for c in chunks)


def test_retrieval_finds_relevant_section(retriever):
    top = retriever.search("¿Hasta cuándo puedo cancelar la cita sin pagar?", k=3)
    assert top[0].id == "citas-y-cancelaciones#cancelar-o-cambiar-una-cita"


def test_retrieval_ignores_accents_and_case(retriever):
    top = retriever.search("HORARIO SABADOS", k=2)
    assert top[0].id == "horarios-y-ubicacion#horario-de-atencion"


def test_retrieval_returns_nothing_for_unrelated_text(retriever):
    assert retriever.search("xyzzy qwerty", k=3) == []


def test_load_chunks_from_empty_dir(tmp_path):
    assert load_chunks(tmp_path) == []
