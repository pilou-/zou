from zou.app.models.entity import Entity, EntityLink


def get_casting(shot):
    casting = []
    links = EntityLink.get_all_by(entity_in_id=shot.id)
    for link in links:
        casting.append({
            "asset_id": str(link.entity_out_id),
            "nb_occurences": link.nb_occurences
        })
    return casting


def update_casting(shot, casting):
    shot.update({"entities_out": []})
    for cast in casting:
        EntityLink.create(
            entity_in_id=shot.id,
            entity_out_id=cast["asset_id"],
            nb_occurences=cast["nb_occurences"]
        )
    shot = Entity.get(shot.id)
    return casting
