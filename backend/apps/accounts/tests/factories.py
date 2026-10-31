import factory

from apps.accounts.models import ApprovalStatus, Role, User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    role = Role.CITIZEN
    approval_status = ApprovalStatus.APPROVED
    is_active = True
    is_superuser = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "SecureP@ssw0rd123!")
        user = super()._create(model_class, *args, **kwargs)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
