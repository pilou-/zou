from sqlalchemy_utils import UUIDType
from zou.app import db
from zou.app.models.serializer import SerializerMixin
from zou.app.models.base import BaseMixin

association_table = db.Table(
    'assignations',
    db.Column('task', UUIDType(binary=False), db.ForeignKey('task.id')),
    db.Column('person', UUIDType(binary=False), db.ForeignKey('person.id'))
)


class Task(db.Model, BaseMixin, SerializerMixin):
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200))

    duration = db.Column(db.Integer)
    estimation = db.Column(db.Integer)
    completion_rate = db.Column(db.Integer)
    sort_order = db.Column(db.Integer)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime)
    real_start_date = db.Column(db.DateTime)
    shotgun_id = db.Column(db.Integer)

    project_id = \
        db.Column(UUIDType(binary=False), db.ForeignKey('project.id'))
    task_type_id = \
        db.Column(UUIDType(binary=False), db.ForeignKey('task_type.id'))
    task_status_id = \
        db.Column(UUIDType(binary=False), db.ForeignKey('task_status.id'))
    entity_id = \
        db.Column(UUIDType(binary=False), db.ForeignKey('entity.id'))
    assigner_id = \
        db.Column(UUIDType(binary=False), db.ForeignKey('person.id'))

    assignees = db.relationship(
        'Person',
        secondary=association_table
    )

    __table_args__ = (
        db.UniqueConstraint(
            'name',
            'project_id',
            'task_type_id',
            'entity_id',
            name='task_uc'
        ),
    )

    def assignees_as_string(self):
        return ", ".join([x.full_name() for x in self.assignees])
