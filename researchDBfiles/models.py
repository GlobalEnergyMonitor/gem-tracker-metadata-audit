from autoslug import AutoSlugField
from django.contrib.postgres.fields import ArrayField
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django_countries.fields import CountryField
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.indexes import GinIndex
from django.db.models.signals import post_save
from functools import lru_cache

tbd_help_text = "If not yet researched, leave as TBD."
cnd_help_text = "If cannot find, mark 'Could not determine'."

from django.contrib.auth.models import User


def add_user_settings(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.create(user=instance, projectType=1)


post_save.connect(add_user_settings, sender=settings.AUTH_USER_MODEL)


PROJECT_TYPES = (
    (1, 'combustion'),
    (2, 'solar'),
    (3, 'wind'),
    (4, 'nuclear'),
    (5, 'geothermal'),
    (6, 'steel'),
    (7, 'hydro'),
    (8, 'lng'),
    (9, 'goget'),
)

NOT_FOUND_YES_N0_CHOICES = [
    ('Y', 'Yes'),
    ('N', 'No'),
    ('NF', 'Not found'),
]

DATA_CENTER_PPA_CHOICES = [
    ('yes', 'yes'),
]

# Options for the structured "Coal Source" select (PowerUnit.coalSourceCategory).
# Kept in sync with the hardcoded <option>s in templates/form/fuel.html.
COAL_SOURCE_CHOICES = [
    ("domestic", "domestic"),
    ("imported", "imported"),
    ("domestic/imported", "domestic/imported"),
    ("unknown", "unknown"),
]


class ProjectType(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'project_type'

    name = models.TextField(
        "Project type name",
        unique=True,
    )

    def __str__(self):
        return self.name


class UserSettings(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'user_settings'
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    projectType = models.IntegerField(
        choices=PROJECT_TYPES,
        null=False,
        default=1
    )

class DataSource(models.Model):
    """
    Linked to various attributes through ManyToManyFields (M2M),
    such as PowerUnit.fuel, PowerUnit.status, etc.
    """
    codelist_table = False
    class Meta:
        db_table = 'data_source'
        indexes = [
            models.Index(fields=["url"]),
        ]

    url = models.TextField(
        "URL",
        null=True,
    )

    shortName = models.TextField(
        "Short name",
        unique=True,
        # help_text="Short name is unique; used in wiki markup as ref name",
    )

    pageTitle = models.TextField(
        "Page Title",
        null=True,
    )

    pageAuthor = models.TextField(
        "Page Author",
        null=True,
    )

    websiteTitle = models.TextField(
        "Website Title",
        null=True,
    )

    publicationDate = models.TextField(
        "Publication Date",
        null=True,
    )

    accessDate = models.TextField(
        "Access Date",
        null=True,
    )

    urlArchived = models.TextField(
        "Data source URL (archived)",
        null=True,
    )

    archivedDate = models.TextField(
        "Archive Date",
        null=True,
    )

    urlStatus = models.TextField(
        "URL Status",
        null=True,
    )

    urlWithQuery = models.TextField(
        "Data source URL, no protocal with query",
        null=True,
    )

    urlNoQuery = models.TextField(
        "Data source URL, no protocal no query",
        null=True,
    )

    created = models.DateTimeField(
        auto_now_add=True,
        null=False
    )

    def __str__(self):
        return self.shortName


class OrgId(models.Model):
    codelist_table = True
    class Meta:
        verbose_name = "Organization Identifier"
        verbose_name_plural = "Organization Identifiers"
        db_table = 'org_id'

    code = models.TextField(
        "code",
    )

    name = models.TextField(
        "name",
    )

    data = models.JSONField(
        "data",
    )

    def __str__(self):
        return self.name


class ExternalIdSystem(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'external_id_system'

    name = models.TextField(
        "External system code",
    )

    region = models.TextField(
        "region",
        null=True,
    )

    def __str__(self):
        return self.name


class FuelCategory(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'fuel_category'
        verbose_name = "Fuel Category"
        verbose_name_plural = "Fuel Categories"

    name = models.TextField(
        "Fuel Category name",
        unique=True,
    )

    def __str__(self):
        return self.name


class Status(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'status'

    name = models.TextField(
    )

    order = models.IntegerField(
        default=100
    )

    def __str__(self):
        return self.name


class Technology(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'technology'

    name = models.TextField(
        "Technology",
    )

    fuel_category = models.ManyToManyField(
        FuelCategory,
    )

    def __str__(self):
        return self.name



class FuelDetail(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'fuel_detail'

    detail = models.TextField(
        "Fuel detail",
    )

    category = models.ForeignKey(
        FuelCategory,
        on_delete=models.CASCADE,
        # help_text="Plant that contains this unit",
    )
    def __str__(self):
        return self.detail


class EntityStatus(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'entity_status'

    status = models.TextField(
        "Entity Status",
        default="",
        null=True,
    )

    def __str__(self):
        return self.status


class Country(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'country'

    isoName = models.TextField(
        null=True,
    )

    gemName = models.TextField(
        null=True,
    )

    isoCode = models.TextField(
        null=True,
    )

    isoCodeAlpha2 = models.TextField(
        null=True,
    )

    isoCodeAlpha3 = models.TextField(
        null=True,
    )

    sameAsIso = models.TextField(
        null=True,
    )

    territory = models.TextField(
        null=True,
    )

    territoryOf = models.TextField(
        null=True,
    )

    region = models.TextField(
        null=True,
    )

    weoRegion = models.TextField(
        null=True,
    )

    subRegion = models.TextField(
        null=True,
    )


class CountrySubdivision(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'country_subdivision'

    isoCode = models.TextField(
        null=True,
    )

    subdivisionIsoCode = models.TextField(
        null=True,
    )

    name = models.TextField(
        null=True,
    )

    category = models.TextField(
        null=True,
    )


class ProjectCountrySubdivision(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'project_country_subdivision'
        constraints = [
            models.UniqueConstraint(fields=['country', 'subdivisionIsoCode'], name='unique_project_country_subdivision'),
        ]

    country = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.PROTECT,
    )

    subdivisionIsoCode = models.TextField(
        null=True,
    )

    name = models.TextField(
        null=True,
    )

    nameLocalVariation = models.TextField(
        null=True,
    )

    category = models.TextField(
        null=True,
    )

    latestIsoUpdate = models.DateField(
        null=True,
    )

    boundarySource = models.TextField(
        null=True,
    )

    latitude = models.DecimalField(
        max_digits=11,
        decimal_places=7,
        null=True,
    )

    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=7,
        null=True,
    )


class EntityType(models.Model):
    codelist_table = True
    class Meta:
        verbose_name_plural = "entity type"
        db_table = 'entity_type'

    type = models.TextField(
        "Entity Type",
        default="",
        null=True,
    )

    def __str__(self):
        return self.type


class LegalEntityType(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'legal_entity_type'

    type = models.TextField(
        "type",
        null=True,
    )

    description = models.TextField(
        "description",
        null=True,
        blank=True,
    )

    countries = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
    )

class CCS(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'ccs'

    option = models.TextField(
        "option",
        null=True,
    )

class CHP(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'chp'

    option = models.TextField(
        "option",
        null=True,
    )

class HydrogenCapable(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'hydrogen_capable'

    option = models.TextField(
        "option",
        null=True,
    )

class HydrogenGenerating(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'hydrogen_generating'

    option = models.TextField(
        "option",
        null=True,
    )

class HydrogenGreenwashing(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'hydrogen_greenwashing'

    option = models.TextField(
        "option",
        null=True,
    )

class CaptiveIndustryType(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'captive_industry_type'

    option = models.TextField(
        "option",
        null=True,
    )

class CaptiveIndustryUse(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'captive_industry_use'

    option = models.TextField(
        "option",
        null=True,
    )

class CaptiveNonIndustryUse(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'captive_non_industry_use'

    option = models.TextField(
        "option",
        null=True,
    )


class CapacityRating(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'capacity_rating'

    option = models.TextField(
        "option",
        null=True,
    )


class InstallationType(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'installation_type'

    option = models.TextField(
        "option",
        null=True,
    )


class UltimateParentRationale(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'ultimate_parent_rationale'

    option = models.TextField(
        null=True,
    )


class EntityTag(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'entity_tag'

    name = models.TextField(
        "Entity tag",
        default="",
    )

    def __str__(self):
        return self.name


class Entity(models.Model):
    codelist_table = False
    class Meta:
        verbose_name_plural = "companies"
        db_table = 'company'
        indexes = [
            GinIndex(
                SearchVector("notes", config="english"),
                name="entity_notes_vector_idx",
            )
        ]

    name = models.TextField(
        "Entity name",
        default="",
        null=True,
    )

    name_local = models.TextField(
        "Entity name (local)",
        default="",
        blank=True,
        null=True,
    )

    nameOther = models.JSONField(
        "Other name(s)",
        default=list,
        null=True,
    )

    name_search = models.TextField(
        "Entity Search",
        default="",
        blank=True,
        null=True,
    )

    entityType = models.ForeignKey(
        EntityType,
        null=True,
        on_delete=models.PROTECT,
    )

    legalEntityType = models.ForeignKey(
        LegalEntityType,
        null=True,
        on_delete=models.PROTECT,
    )

    homepage = models.TextField(
        null=True,
    )

    notes = models.TextField(
        null=True,
    )

    country = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.PROTECT,
    )

    subdivision = models.ForeignKey(
        CountrySubdivision,
        null=True,
        on_delete=models.SET_NULL,
    )

    headquarters_country = models.ForeignKey(
        Country,
        null=True,
        related_name='+',
        on_delete=models.PROTECT,
    )

    headquarters_subdivision = models.ForeignKey(
        CountrySubdivision,
        null=True,
        related_name='+',
        on_delete=models.SET_NULL,
    )


    ultimateParent = models.BooleanField(
        null=True,
    )

    ultimateParentRationale = models.ForeignKey(
        UltimateParentRationale,
        null=True,
        on_delete=models.PROTECT,
    )

    defunct = models.BooleanField(
        null=True,
    )

    entityStatus = models.ForeignKey(
        EntityStatus,
        null=True,
        on_delete=models.PROTECT,
    )

    entityStatusDatasource = models.JSONField(
        null=True,
        default=list
    )

    mergedInto = models.BigIntegerField(
        null=True,
    )

    mergersAcquisitions = models.TextField(
        null=True,
    )

    abbreviation = models.TextField(
        "Abbreviation",
        default="",
        blank=True,
        null=True,
    )

    publiclyListed = models.TextField(
        "publiclyListed",
        default="",
        blank=True,
        null=True,
    )

    jointVenture = models.TextField(
        "jointVenture",
        default="False",
        null=True,
    )

    tag = models.ForeignKey(
        EntityTag,
        null=True,
        on_delete=models.PROTECT,
    )

    modified = models.DateTimeField(
        auto_now=True,
        null=False
    )

    created = models.DateTimeField(
        auto_now_add=True,
        null=False
    )

    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='+',
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )

    deleted = models.BooleanField(
        default=False,
        null=False
    )

    deletedTimestamp = models.DateTimeField(
        null=True
    )

    entityJSON = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True
    )

    gemParents = models.TextField(
        null=True
    )

    endOfBranches = models.TextField(
        null=True
    )

    gemParentsIds = models.TextField(
        null=True
    )

    endOfBranchesIds = models.TextField(
        null=True
    )

    def __str__(self):
        return self.name


class NuclearModel(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'nuclear_model'

    name = models.TextField(
        "Nuclear model",
        default="",
    )

    def __str__(self):
        return self.name




class EntityOrgId(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'entity_org_id'

    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        null=True
    )

    orgId = models.ForeignKey(
        OrgId,
        on_delete=models.CASCADE,
        null=True
    )

    value = models.TextField(
        "value",
        null=True,
    )

    datasource = models.TextField(
        "datasource",
        null=True,
    )


class Plant(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'plant'
        constraints = [
            models.UniqueConstraint(fields=['name'], condition=models.Q(deleted=False), name='unique_name_contraint'),
        ]
        indexes = [
            GinIndex(
                SearchVector("notes", config="english"),
                name="notes_vector_idx",
            )
        ]

    projectType = models.IntegerField(
        choices=PROJECT_TYPES,
        null=False,
        default=1
    )

    name = models.TextField(
        "Plant name",
    )

    nameSearch = models.TextField(
        null=True
    )

    subnationalSearch = models.TextField(
        null=True
    )

    citySearch = models.TextField(
        null=True
    )

    localAreaSearch = models.TextField(
        null=True
    )

    majorAreaSearch = models.TextField(
        null=True
    )

    countrySearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    fuelCategorySearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    fuelDetailSearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    statusSearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    unitIDSearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    ownerSearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    operatorSearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    externalIDSearch = models.TextField(
        null=True
    )

    plantJSON = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True
    )

    slug = AutoSlugField(
        unique=True,
        always_update=False,
        populate_from="name",
    )

    nameOther = models.JSONField(
        "Other name(s)",
        default=list,
        null=True,
    )

    wikiUrl = models.TextField(
        "Wiki URL",
        null=True,
    )

    notes = models.TextField(
        null=True,
    )

    plantLevelOperators = models.BooleanField(
        null=True,
        default=True
    )

    plantLevelOwners = models.BooleanField(
        null=True,
    )

    plantLevelLocation = models.BooleanField(
        null=True,
    )

    streetAddress = models.TextField(
        null=True
    )

    streetAddress2 = models.TextField(
        null=True
    )

    city = models.TextField(
        null=True
    )

    city2 = models.TextField(
        null=True
    )

    localArea = models.TextField(
        null=True
    )

    localArea2 = models.TextField(
        null=True
    )

    majorArea = models.TextField(
        null=True
    )

    majorArea2 = models.TextField(
        null=True
    )

    subnational = models.TextField(
        null=True
    )

    subnationalLookup = models.ForeignKey(
        ProjectCountrySubdivision,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    subnationalServiceResults = models.ForeignKey(
        ProjectCountrySubdivision,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    subnational2 = models.TextField(
        null=True
    )

    subnational2Lookup = models.ForeignKey(
        ProjectCountrySubdivision,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    subnational2ServiceResults = models.ForeignKey(
        ProjectCountrySubdivision,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    country = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.SET_NULL,
    )

    country2 = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    country3 = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    country4 = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    country5 = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    country6 = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    country7 = models.ForeignKey(
        Country,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    binational = models.BooleanField(
        null=True,
    )

    multinational = models.BooleanField(
        null=True,
    )

    complex = models.TextField(
        null=True,
    )

    complexDatasource = models.JSONField(
        null=True,
        default=list
    )

    coordinateFormat = models.TextField(
        null=True,
    )

    coordinateFormatOther = models.TextField(
        null=True,
    )

    locationDatasource = models.JSONField(
        null=True,
        default=list
    )

    latitude = models.DecimalField(
        max_digits=11,
        decimal_places=7,
        null=True,
    )

    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=7,
        null=True,
    )

    latitudeText = models.TextField(
        null=True,
    )

    longitudeText = models.TextField(
        null=True,
    )

    locationAccuracy = models.TextField(
        null=True,
    )

    subnationalChecked = models.BooleanField(
        default=False,
        null=False,
    )

    captive = models.BooleanField(
        null=True,
        default=False
    )

    captiveIndustryType = models.JSONField(
        null=True,
        default=list
    )

    captiveIndustryUse = models.ForeignKey(
        CaptiveIndustryUse,
        null=True,
        on_delete=models.SET_NULL,
    )

    captiveNonIndustryUse = models.ForeignKey(
        CaptiveNonIndustryUse,
        null=True,
        on_delete=models.SET_NULL,
    )

    captiveDatasource = models.JSONField(
        null=True,
        default=list
    )

    backupPower = models.BooleanField(
        null=True,
        default=False
    )

    backupPowerDatasource = models.JSONField(
        "Backup Power",
        null=True,
        default=list
    )

    employmentNotes = models.TextField(
        null=True
    )

    employmentNotesDatasource = models.JSONField(
        null=True,
        default=list
    )

    projectLinkDatasource = models.JSONField(
        null=True,
        default=list
    )

    validation = models.JSONField(
        null=True,
        default=dict
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )

    deleted = models.BooleanField(
        default=False,
        null=False
    )

    deletedTimestamp = models.DateTimeField(
        null=True
    )

    modified = models.DateTimeField(
        auto_now=True,
        null=False
    )

    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='+',
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """Return absolute URL to the Power Plant detail page."""
        return reverse("powerplants:detail", kwargs={"slug": self.slug})


class PowerUnit(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'powerplant_unit'
        constraints = [
            models.UniqueConstraint(fields=["plant", "name"], condition=models.Q(deleted=False), name='unique_unit_name_project_contraint'),
        ]
        indexes = [
            GinIndex(
                SearchVector("statusDetail", config="english"),
                name="powerunit_statusdetail_fts_idx",
            )
        ]

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
    )

    name = models.TextField(
        "Name",
    )

    # Capacity
    capacity = models.DecimalField(
        "Capacity",
        max_digits=20,
        decimal_places=1,
        null=True,
    )

    partialCapacity1 = models.DecimalField(
        "Partial Capacity",
        max_digits=20,
        decimal_places=1,
        null=True,
    )

    partialCapacity2 = models.DecimalField(
        "Partial Capacity",
        max_digits=20,
        decimal_places=1,
        null=True,
    )

    capacityPerEngine = models.DecimalField(
        "Capacity Per Engine",
        max_digits=20,
        decimal_places=1,
        null=True,
    )

    numberOfEngines = models.IntegerField(
        "Number Of Engines",
        null=True,
    )

    capacityDatasource = models.JSONField(
        "Capacity Datasource",
        null=True,
        default=list
    )

    fuelConversion = models.BooleanField(
        null=True,
    )

    fuelDatasource = models.JSONField(
        "Category Datasource",
        null=True,
        default=list
    )

    turbine = models.TextField(
        null=True,
    )

    watercourse = models.TextField(
        null=True,
    )

    watercourseDatasource = models.JSONField(
        null=True,
        default=list
    )

    turbineDatasource = models.JSONField(
        null=True,
        default=list
    )

    capacityRating = models.ForeignKey(
        CapacityRating,
        on_delete=models.PROTECT,
        null=True
    )

    capacityRatingDatasource = models.JSONField(
        "Capacity Rating Datasource",
        null=True,
        default=list
    )

    thermalCapacity = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
    )

    thermalCapacityDatasource = models.JSONField(
        "Capacity Rating Datasource",
        null=True,
        default=list
    )

    designNetCapacity = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
    )

    designNetCapacityDatasource = models.JSONField(
        "Capacity Rating Datasource",
        null=True,
        default=list
    )

    referenceNetCapacity = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
    )

    referenceNetCapacityDatasource = models.JSONField(
        "Capacity Rating Datasource",
        null=True,
        default=list
    )

    installationType = models.ForeignKey(
        InstallationType,
        on_delete=models.PROTECT,
        null=True
    )

    installationTypeDatasource = models.JSONField(
        "Installation Type Datasource",
        null=True,
        default=list
    )

    # Free-text coal source, rendered in the form/exports as "Coal Source Notes".
    # (The structured "Coal Source" value lives in coalSourceCategory below.)
    coalSource = models.TextField(
        null=True
    )

    # Structured coal source, rendered as "Coal Source": a single choice from
    # COAL_SOURCE_CHOICES (domestic / imported / domestic/imported / unknown).
    coalSourceCategory = models.TextField(
        null=True,
        choices=COAL_SOURCE_CHOICES,
    )

    # "minemouth" coal plant flag (rendered alongside the coal source fields).
    minemouth = models.BooleanField(
        null=True,
        default=False
    )

    hydrogenGenerating = models.ForeignKey(
        HydrogenGenerating,
        on_delete=models.PROTECT,
        null=True
    )

    hydrogenProducing = models.BooleanField(
        null=True,
    )

    hydrogenProducingDatasource = models.JSONField(
        "Green Hydrogen Producing",
        null=True,
        default=list
    )

    dataCenterPPA = models.TextField(
        null=True,
        choices=DATA_CENTER_PPA_CHOICES,
    )

    dataCenterPPADatasource = models.JSONField(
        "Data Center PPA",
        null=True,
        default=list
    )

    permitted = models.BooleanField(
        null=True,
    )

    permitDetails = models.TextField(
        null=True
    )

    permitYear = models.IntegerField(
        null=True
    )

    permitMonth = models.IntegerField(
        null=True
    )

    permitDay = models.IntegerField(
        null=True
    )

    permitDatasource = models.JSONField(
        "Permit Datasource",
        null=True,
        default=list
    )

    technology = models.JSONField(
        "Technology",
        null=True,
        default=list
    )

    technologyDatasource = models.JSONField(
        null=True,
        default=list
    )

    streetAddress = models.TextField(
        null=True
    )

    city = models.TextField(
        null=True
    )

    localArea = models.TextField(
        null=True
    )

    majorArea = models.TextField(
        null=True
    )

    subnational = models.TextField(
        null=True
    )

    subnationalLookup = models.ForeignKey(
        ProjectCountrySubdivision,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    subnationalServiceResults = models.ForeignKey(
        ProjectCountrySubdivision,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    coordinateFormat = models.TextField(
        null=True,
    )

    coordinateFormatOther = models.TextField(
        null=True,
    )

    locationDatasource = models.JSONField(
        null=True,
        default=list
    )

    latitude = models.DecimalField(
        max_digits=11,
        decimal_places=7,
        null=True,
    )

    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=7,
        null=True,
    )

    latitudeText = models.TextField(
        null=True,
    )

    longitudeText = models.TextField(
        null=True,
    )

    locationAccuracy = models.TextField(
        null=True,
    )

    subnationalChecked = models.BooleanField(
        default=False,
        null=False,
    )

    captive = models.BooleanField(
        null=True,
        default=False
    )

    captiveIndustryType = models.JSONField(
        null=True,
        default=list
    )

    captiveIndustryUse = models.ForeignKey(
        CaptiveIndustryUse,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    captiveNonIndustryUse = models.ForeignKey(
        CaptiveNonIndustryUse,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    captiveDatasource = models.JSONField(
        null=True,
        default=list
    )

    backupPower = models.BooleanField(
        null=True,
        default=False
    )

    backupPowerDatasource = models.JSONField(
        "Backup Power",
        null=True,
        default=list
    )

    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        null=True
    )

    statusDetail = models.TextField(
        null=True
    )

    latestActivityYear = models.IntegerField(
        null=True
    )

    latestActivityMonth = models.IntegerField(
        null=True
    )

    latestActivityDay = models.IntegerField(
        null=True
    )

    latestActivityDatasource = models.JSONField(
        null=True,
        default=list
    )

    ccsAttachment = models.ForeignKey(
        CCS,
        on_delete=models.PROTECT,
        null=True
    )

    chp = models.ForeignKey(
        CHP,
        on_delete=models.PROTECT,
        null=True
    )

    ccsDatasource = models.JSONField(
        null=True,
        default=list
    )

    chpDatasource = models.JSONField(
        null=True,
        default=list
    )

    hydrogenCapable = models.ForeignKey(
        HydrogenCapable,
        on_delete=models.PROTECT,
        null=True
    )

    hydrogenCapableDatasource = models.JSONField(
        null=True,
        default=list
    )

    hydrogenGreenwashing = models.ForeignKey(
        HydrogenGreenwashing,
        on_delete=models.PROTECT,
        null=True
    )

    hydrogenNotes = models.TextField(
        null=True
    )

    statusDatasource = models.JSONField(
        null=True,
        default=list
    )

    disruptedDueToConflict = models.BooleanField(
        null=True,
        default=False
    )

    disruptedDueToConflictDatasource = models.JSONField(
        null=True,
        default=list
    )

    startYearLow = models.IntegerField(
        null=True

    )

    startYearMonth = models.IntegerField(
        null=True
    )

    startYearDay = models.IntegerField(
        null=True
    )

    startYearHigh = models.IntegerField(
        null=True
    )

    startYearPlanned = models.BooleanField(
        null=True,
        default=False
    )

    startYearDatasource = models.JSONField(
        null=True,
        default=list
    )

    endYearLow = models.IntegerField(
        null=True
    )

    endYearMonth = models.IntegerField(
        null=True
    )

    endYearDay = models.IntegerField(
        null=True
    )

    endYearHigh = models.IntegerField(
        null=True
    )

    endYearPlanned = models.BooleanField(
        null=True,
        default=False
    )

    endYearDatasource = models.JSONField(
        null=True,
        default=list
    )

    cancellationYear = models.IntegerField(
        null=True
    )

    cancellationYearDatasource = models.JSONField(
        null=True,
        default=list
    )

    plannedStartYear = models.IntegerField(
        null=True
    )

    overdueStart = models.BooleanField(
        null=True,
        default=False
    )

    plannedStartDatasource = models.JSONField(
        null=True,
        default=list
    )

    plannedRetiredYear = models.IntegerField(
        null=True
    )

    overdueRetired = models.BooleanField(
        null=True,
        default=False
    )

    plannedRetiredDatasource = models.JSONField(
        null=True,
        default=list
    )

    firstGridConnectionYear = models.IntegerField(
        null=True
    )

    firstGridConnectionMonth = models.IntegerField(
        null=True
    )

    firstGridConnectionDay = models.IntegerField(
        null=True
    )

    firstGridConnectionDatasource = models.JSONField(
        null=True,
        default=list
    )

    firstCriticalityYear = models.IntegerField(
        null=True
    )

    firstCriticalityMonth = models.IntegerField(
        null=True
    )

    firstCriticalityDay = models.IntegerField(
        null=True
    )

    firstCriticalityDatasource = models.JSONField(
        null=True,
        default=list
    )

    constructionStartYear = models.IntegerField(
        null=True
    )

    constructionStartMonth = models.IntegerField(
        null=True
    )

    constructionStartDay = models.IntegerField(
        null=True
    )

    constructionStartDatasource = models.JSONField(
        null=True,
        default=list
    )

    nameLocal = models.TextField(
        null=True
    )

    operatorPrimary = models.ForeignKey(
        Entity,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+'
    )

    ownerPrimary = models.ForeignKey(
        Entity,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+'
    )

    nuclearModel = models.ForeignKey(
        NuclearModel,
        on_delete=models.PROTECT,
        null=True
    )

    nuclearModelDatasource = models.JSONField(
        null=True,
        default=list
    )

    trackerSearch = models.TextField(
        null=True,
    )

    subnationalSearch = models.TextField(
        null=True
    )

    citySearch = models.TextField(
        null=True
    )

    localAreaSearch = models.TextField(
        null=True
    )

    majorAreaSearch = models.TextField(
        null=True
    )

    countrySearch = models.BigIntegerField(
        null=True
    )

    fuelCategorySearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    fuelDetailSearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    ownerSearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    operatorSearch = ArrayField(
        models.BigIntegerField(),
        null=True
    )

    nameSearch = models.TextField(
        null=True
    )

    lastUpdatedSearch = models.TextField(
        null=True
    )

    researcherSearch = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
    )

    researchStatusSearch = models.ForeignKey(
        'ResearchStatus',
        null=True,
        on_delete=models.SET_NULL,
    )

    externalIDSearch = models.TextField(
        null=True
    )

    fuelConversionInitialUnit = models.ForeignKey(
        'PowerUnit',
        on_delete=models.PROTECT,
        null=True
    )

    associatedStorage = models.BooleanField(
        null=True
    )

    associatedStorageDatasource = models.JSONField(
        null=True
    )

    irp = models.BooleanField(
        null=True,
        blank=True,
        default=False,
    )

    fuelConversionUnknown = models.BooleanField(
        null=True
    )

    unitJSON = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True
    )

    deleted = models.BooleanField(
        default=False
    )

    deletedTimestamp = models.DateTimeField(
        null=True
    )

    H2ReadyTurbine = models.IntegerField(
        null=True,
    )

    MOUH2Supply = models.TextField(
        choices=NOT_FOUND_YES_N0_CHOICES,
        null=True,
    )

    contractH2Supply = models.TextField(
        choices=NOT_FOUND_YES_N0_CHOICES,
        null=True,
    )

    financingH2Supply = models.TextField(
        choices=NOT_FOUND_YES_N0_CHOICES,
        null=True,
    )

    colocatedWithProduction = models.TextField(
        choices=NOT_FOUND_YES_N0_CHOICES,
        null=True,
    )

    percentageBlending = models.IntegerField(
        null=True
    )

    H2CriteriaDatasource = models.JSONField(
        null=True,
        default=list
    )   

    statusSearch = models.TextField(
        null=True
    )
        

class UnitFuel(models.Model):
    codelist_table = False
    class Meta:
        verbose_name_plural = "unit fuel"
        db_table = 'unit_fuel'

    powerplant_unit = models.ForeignKey(
        PowerUnit,
        on_delete=models.CASCADE,
        null=True
    )

    primary = models.BooleanField(
        null=True,
    )

    category = models.ForeignKey(
        FuelCategory,
        on_delete=models.PROTECT,
        null=True
    )

    detail = models.ForeignKey(
        FuelDetail,
        on_delete=models.PROTECT,
        null=True
    )

    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        null=True
    )


    startYear = models.TextField(
        null=True
    )

    timepoint = models.TextField(
        null=True
    )

    percentage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
    )

TIMELINE_STATUS_COMBUSTION = { 
    "operating": [],
    "announced": [],
    "pre-construction": ["pre-permit", "permitted"],
    "construction": [],
    "shelved": ["inferred"],
    "mothballed": [],
    "retired/fuel switch": ['fuel switch'],
    "cancelled": ["inferred"],
}

TIMELINE_STATUS_LNG = { 
    "proposed": [],
    "construction": ["actual", "planned"],
    "operating": ["actual", "planned"],
    "shelved": ["confirmed", "inferred 2 y"],
    "cancelled": ["confirmed","inferred 4 y"],
    "idled": ["actual", "planned"],
    "mothballed": ["actual", "planned"],
    "retired": ["actual", "planned"],
    "FID": ["actual", "planned"],
}

TIMELINE_STATUS_GOGET = { 
    'operating': ['', 'planned', 'ramp up', 'plateau', 'decline'],
    'exploration': [],
    'discovered': ['', 'early', 'advanced'],
    'in-development': ['', 'planned', 'actual FID'],
    'cancelled': ['', 'assumed', 'stated'],
    'decommissioning': ['', 'planned', 'in progress', 'complete'],
    'underground gas storage': [],
    'underground carbon storage': ['', 'proposed', 'operating'],
    'mothballed': ['', 'assumed', 'stated'],
    'abandoned': ['', 'assumed', 'stated'],
}

TIMELINE_STATUS_COMBUSTION_CHOICES = [
    (status, status) for status in TIMELINE_STATUS_COMBUSTION.keys()
]

TIMELINE_STATUS_LNG_CHOICES = [
    (status, status) for status in TIMELINE_STATUS_LNG.keys()
]

TIMELINE_STATUS_GOGET_CHOICES = [
    (status, status) for status in TIMELINE_STATUS_GOGET.keys()
]

TIMELINE_STATUS_CHOICES = TIMELINE_STATUS_COMBUSTION_CHOICES + TIMELINE_STATUS_LNG_CHOICES + TIMELINE_STATUS_GOGET_CHOICES

TIMELINE_SUBSTATUS_CHOICES = []

for status, substatus in TIMELINE_STATUS_COMBUSTION.items():
    for substatus in substatus:
        TIMELINE_SUBSTATUS_CHOICES.append((substatus, substatus))
for status, substatus in TIMELINE_STATUS_LNG.items():
    for substatus in substatus:
        TIMELINE_SUBSTATUS_CHOICES.append((substatus, substatus))
for status, substatus in TIMELINE_STATUS_GOGET.items():
    for substatus in substatus:
        TIMELINE_SUBSTATUS_CHOICES.append((substatus, substatus))


MONTH_HALF_YEAR_CHOICES = [
    ('H1', 'H1'),
    ('H2', 'H2'),
    ('Q1', 'Q1'),
    ('Q2', 'Q2'),
    ('Q3', 'Q3'),
    ('Q4', 'Q4'),
    ('January', 'January'),
    ('February', 'February'),
    ('March', 'March'),
    ('April', 'April'),
    ('May', 'May'),
    ('June', 'June'),
    ('July', 'July'),
    ('August', 'August'),
    ('September', 'September'),
    ('October', 'October'),
    ('November', 'November'),
    ('December', 'December'),
]


class StatusTimeline(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'status_timeline'
    
    unit = models.ForeignKey(
        PowerUnit,
        on_delete=models.PROTECT,
    )

    order = models.IntegerField(
        null=False
    )

    status = models.TextField(
        Status,
        choices=TIMELINE_STATUS_CHOICES,
        null=True,
    )

    substatus = models.TextField(
        choices = TIMELINE_SUBSTATUS_CHOICES,
        null=True,
    )

    statusDatasource = models.JSONField(
        "Status Datasource",
        null=True,
        default=list
    )

    year = models.IntegerField(
        null=True,
    )

    monthOrHalfYear = models.TextField(
        null=True,
        choices=MONTH_HALF_YEAR_CHOICES,
    )

    delayed = models.BooleanField(
        null=True,
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )

    created = models.DateTimeField(
        auto_now_add=True,
        null=False
    )

    modified = models.DateTimeField(
        auto_now=True
    )


class Operator(models.Model):
    codelist_table = False
    class Meta:
        verbose_name_plural = "plant owners"
        db_table = 'operator'

    company = models.ForeignKey(
        Entity,
        on_delete=models.PROTECT,
        null=False
    )

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        null=True
    )

    powerplant_unit = models.ForeignKey(
        PowerUnit,
        on_delete=models.CASCADE,
        null=True
    )

    operatorDatasource = models.JSONField(
        "Operator Datasource",
        null=True,
        default=list
    )

    type = models.TextField(
        "type",
        null=True,
        blank=True
    )

    share = models.DecimalField(
        "share",
        max_digits=10,
        decimal_places=2,
        null=True,
    )


class PlantOwner(models.Model):
    codelist_table = False
    class Meta:
        verbose_name_plural = "plant owners"
        db_table = 'plant_owner'

    share = models.DecimalField(
        "share",
        max_digits=10,
        decimal_places=2,
        null=True,
    )

    impliedShare = models.DecimalField(
        "impliedShare",
        blank=True,
        max_digits=10,
        decimal_places=2,
        null=True,
    )

    company = models.ForeignKey(
        Entity,
        on_delete=models.PROTECT,
        null=False
    )

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        null=True
    )

    powerplant_unit = models.ForeignKey(
        PowerUnit,
        on_delete=models.CASCADE,
        null=True
    )

    shareDatasource = models.JSONField(
        "Share Datasource",
        null=True,
        default=list
    )

SHARE_RANGES = [
    ('≤ 25%', '≤ 25%'),
    ('> 25% & ≤ 50%', '> 25% & ≤ 50%'),
    ('> 50% & < 75%', '> 50% & < 75%'),
    ('≥ 75%', '≥ 75%'),
]

class EntityOwner(models.Model):
    codelist_table = False
    class Meta:
        verbose_name_plural = "company owners"
        db_table = 'company_owner'

    share = models.DecimalField(
        "share",
        blank=True,
        max_digits=5,
        decimal_places=2,
        null=True,
    )

    shareRange = models.TextField(
        "shareRange",
        default="",
        blank=True,
        null=True,
        choices=SHARE_RANGES
    )

    owner = models.ForeignKey(
        Entity,
        on_delete=models.PROTECT,
        null=False,
        related_name='as_owner'
    )

    company = models.ForeignKey(
        Entity,
        on_delete=models.PROTECT,
        null=False,
        related_name='as_owned'
    )

    shareDatasource = models.JSONField(
        "Share Datasource",
        null=True,
        default=list
    )



class Language(models.Model):
    codelist_table = True
    class Meta:
        verbose_name_plural = "languages"
        db_table = 'language'

    name = models.TextField(
        "Language name",
        unique=True,
    )

    def __str__(self):
        return self.name


class PlantLanguage(models.Model):
    codelist_table = False
    class Meta:
        verbose_name_plural = "plant languages"
        db_table = 'plant_language'

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        null=True
    )

    language = models.ForeignKey(
        Language,
        on_delete=models.PROTECT,
        null=True
    )

    name = models.TextField(
        "name",
        null=True,
    )

    wikiUrl = models.TextField(
        "wikiUrl",
        null=True,
    )


class ProjectLinkType(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'project_link_types'

    code = models.TextField(
        unique=True,
    )

    sourceTracker = models.TextField(
        null=True,
    )

    destinationTracker = models.TextField(
        null=True,
    )

    sourceShortName = models.TextField(
        null=True,
    )

    destinationShortName = models.TextField(
        null=True,
    )

    sourceLongName = models.TextField(
        null=True,
    )

    destinationLongName = models.TextField(
        null=True,
    )

    # Any 'yes' value makes the link text-only in the form (the far end is not
    # a project in this database).
    outOfDatabase = models.TextField(
        null=True,
        choices=[
            ('no', 'no'),
            ('yes', 'yes'),
            ('yes - planned migration 2026', 'yes - planned migration 2026'),
        ],
    )

    # Parsed from the seed CSV's Conditions column (migration 0305); edited
    # directly in the admin now that the database is the canonical source.
    # onlyCountry is a Country id (text) the linked projects must be in; the
    # admin form presents it as a country dropdown. lngFacilityType describes
    # the LNG project on whichever side has the 'GGIT LNG' tracker.
    onlyCountry = models.TextField(
        null=True,
    )

    lngFacilityType = models.TextField(
        null=True,
        choices=[
            ('import', 'import'),
            ('export', 'export'),
        ],
    )

    # The same relationship seen from the other side (migration 0305 seeds each
    # CSV row in both directions). NULL means the type is only definable from
    # this direction. Search/reporting union a type with its reciprocal so links
    # entered from either side are found together.
    reciprocal = models.ForeignKey(
        "self",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def __str__(self):
        return self.sourceShortName or self.destinationShortName or self.code


class ProjectLinks(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'project_links'

    project = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        null=True
    )

    linkedProjectText = models.TextField(
        null=True,
    )

    linkedProject = models.ForeignKey(
        Plant,
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
    )

    linkType = models.ForeignKey(
        ProjectLinkType,
        on_delete=models.PROTECT,
        null=True,
    )

    projectLinkDatasource = models.JSONField(
        null=True,
        default=list,
    )


class PlantExternalId(models.Model):
    codelist_table = False
    class Meta:
        verbose_name_plural = "plant external ids"
        db_table = 'plant_external_id'

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        null=True
    )

    idSystem = models.ForeignKey(
        ExternalIdSystem,
        on_delete=models.PROTECT,
        null=True
    )

    externalId = models.TextField(
        "name",
        null=True,
    )

class UnitExternalId(models.Model):
    codelist_table = False
    class Meta:
        verbose_name_plural = "plant external ids"
        db_table = 'unit_external_id'

    unit = models.ForeignKey(
        PowerUnit,
        on_delete=models.CASCADE,
        null=True
    )

    idSystem = models.ForeignKey(
        ExternalIdSystem,
        on_delete=models.CASCADE,
        null=True
    )

    externalId = models.TextField(
        "name",
        null=True,
    )


class PlantHistory(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'plant_history'

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
    )

    plantJSON = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True
    )

    modified = models.DateTimeField(
        auto_now=True
    )

    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )


class EntityHistory(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'entity_history'

    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
    )

    entityJSON = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True
    )

    modified = models.DateTimeField(
        auto_now=True
    )

    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )


class UnitReplacementType(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'unit_replacement_type'

    option = models.TextField(
        null=True,
    )


class UnitReplacement(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'unit_replacement'

    unit = models.ForeignKey(
        PowerUnit,
        on_delete=models.CASCADE,
        null=True
    )

    unitReplacementType = models.ForeignKey(
        UnitReplacementType,
        on_delete=models.PROTECT,
        null=True
    )

    unitReplacementId = models.BigIntegerField(
        null=True,
    )

    unitReplacementDatasource = models.JSONField(
        null=True,
        default=list
    )


class ResearchStatus(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'research_status'

    option = models.TextField(
        null=True,
    )



class UnitUpdate(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'unit_update'

    unit = models.ForeignKey(
        PowerUnit,
        on_delete=models.CASCADE,
        null=True
    )

    researchStatus = models.ForeignKey(
        ResearchStatus,
        on_delete=models.PROTECT,
        null=True
    )

    lastUpdated = models.DateField(
        null=True,
    )

    updater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )


class ProjectUpdate(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'project_update'

    project = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        null=True
    )

    researchStatus = models.ForeignKey(
        ResearchStatus,
        on_delete=models.PROTECT,
        null=True
    )

    lastUpdated = models.DateField(
        null=True,
    )

    updater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )


class EntityUpdate(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'entity_update'

    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        null=True
    )

    researchStatus = models.ForeignKey(
        ResearchStatus,
        on_delete=models.PROTECT,
        null=True
    )

    lastUpdated = models.DateField(
        null=True,
    )

    updater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )




class TurbineManufacturer(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'turbine_manufacturer'

    option = models.TextField(
        null=True,
    )

    deleted = models.BooleanField(default=False)


class UnitTurbine(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'unit_turbine'

    unit = models.ForeignKey(
        PowerUnit,
        on_delete=models.CASCADE,
        null=True
    )

    model = models.TextField(
        null=True,
    )

    turbineManufacturer = models.ForeignKey(
        TurbineManufacturer,
        on_delete=models.PROTECT,
        null=True
    )



class Thread(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'thread'

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
    )

    completed = models.BooleanField(
        default=False
    )

    element = models.TextField(
        null=True,
    )

    project = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        null=True
    )

    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        null=True
    )

    deleted = models.BooleanField(
        default=False
    )

    created = models.DateTimeField(
    )

    modified = models.DateTimeField(
    )



class Comment(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'comment'

    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        null=True
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,  # EXPERIMENTAL
        on_delete=models.SET_NULL,
        related_name='+'
    )

    created = models.DateTimeField(
    )

    comment = models.TextField(
        null=True,
    )

    deleted = models.BooleanField(
        default=False
    )


NOT_FOUND_GT_LT_CHOICES = [
    ('>', 'Greater than'),
    ('<', 'Less than'),
    ('NF', 'Not found'),
    ('NA', 'Not applicable'),
]

NOT_FOUND_YES_CHOICES = [
    ('Y', 'Yes'),
    ('N', 'No'),
    ('NF', 'Not found'),
    ('Expired', 'Expired'),
]


FURNACE_SIZE_UNIT_CHOICES = [
    ('tonnes', 'Tonnes'),
    ('m3', 'Cubic meters'),
]

NOT_FOUND_GREATER_THAN_ZERO = [
    ('>0', 'Greater than'),
    ('NF', 'Not found'),
]

GRANULARITY_CHOICES = [
    ('company', 'company'),
    ('plant', 'plant'),
    ('unit', 'unit')
]

FURNACE_VOLUME_TYPE = [
    ('working', 'Working'),
    ('external', 'External'),
    ('internal', 'Internal'),
    ('NF', 'Not found'),
]

STEEL_PRODUCT_CATEGORY = [
   ('crude', 'Crude'),
   ('semi-finished', 'Semi-finished'),
   ('finished rolled', 'Finished'),
]

END_USERS = [
    ('not found', 'Not found'),
    ('automotive', 'Automotive'),
    ('building and infrastructure', 'Building and infrastructure'),
    ('energy', 'Energy'),
    ('steel packaging', 'Steel packaging'),
    ('tools and machinery', 'Tools and machinery'),
    ('transport', 'Transport'),
]

class SteelProduct(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'steel_product'

    product = models.TextField(null=True, unique=True)

class SteelProject(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'steel_project'
    
    project = models.OneToOneField(Plant, on_delete=models.CASCADE)

    isExcluded = models.BooleanField(null=True, blank=True)
    excludedNotes = models.TextField(null=True, blank=True)

    technologyTransition = models.BooleanField(null=True, blank=True)
    capacitySwap = models.BooleanField(null=True, blank=True)

    carbonMarket = models.BooleanField(null=True, blank=True)
    carbonMarketName = models.TextField(null=True, blank=True)

    wikiBackgroundLastUpdatedYear = models.IntegerField(null=True, blank=True)
    wikiBackgroundLastUpdatedMonth = models.IntegerField(null=True, blank=True)
    wikiBackgroundLastUpdatedDay = models.IntegerField(null=True, blank=True)

    localLanguageAddress = models.TextField(null=True, blank=True)

    companyWebsite = models.TextField(null=True, blank=True)
    wikipediaURL = models.TextField(null=True, blank=True)
    IPEPageURL = models.TextField(null=True, blank=True)
    baiduBaikuURL = models.TextField(null=True, blank=True)

    announcedDay = models.IntegerField(null=True, blank=True)
    announcedMonth = models.IntegerField(null=True, blank=True)
    announcedYear = models.IntegerField(null=True, blank=True)
    announcedDateDatasource = models.JSONField(null=True, blank=True, default=list)

    constructionDay = models.IntegerField(null=True, blank=True)
    constructionMonth = models.IntegerField(null=True, blank=True)
    constructionYear = models.IntegerField(null=True, blank=True)
    constructionDateDatasource = models.JSONField(null=True, blank=True, default=list)

    startDay = models.IntegerField(null=True, blank=True)
    startMonth = models.IntegerField(null=True, blank=True)
    startYear = models.IntegerField(null=True, blank=True)
    startDateDatasource = models.JSONField(null=True, blank=True, default=list)

    preretireAnnouncedDay = models.IntegerField(null=True, blank=True)
    preretireAnnouncedMonth = models.IntegerField(null=True, blank=True)
    preretireAnnouncedYear = models.IntegerField(null=True, blank=True)
    preretireAnnouncedDateDatasource = models.JSONField(null=True, blank=True, default=list)

    idledDay = models.IntegerField(null=True, blank=True)
    idledMonth = models.IntegerField(null=True, blank=True)
    idledYear = models.IntegerField(null=True, blank=True)
    idledDateDatasource = models.JSONField(null=True, blank=True, default=list)

    retiredDay = models.IntegerField(null=True, blank=True)
    retiredMonth = models.IntegerField(null=True, blank=True)
    retiredYear = models.IntegerField(null=True, blank=True)
    retiredDateDatasource = models.JSONField(null=True, blank=True, default=list) 


    ferronickelCapacityQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GT_LT_CHOICES, null=True, blank=True)
    ferronickelCapacity = models.IntegerField(null=True, blank=True)
    ferronickelCapacityDatasource = models.JSONField(null=True, blank=True, default=list)
    sinterCapacityQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GT_LT_CHOICES, null=True, blank=True)
    sinterCapacity = models.IntegerField(null=True, blank=True)
    sinterCapacityDatasource = models.JSONField(null=True, blank=True, default=list)
    cokingCapacityQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GT_LT_CHOICES, null=True, blank=True)
    cokingCapacity = models.IntegerField(null=True, blank=True)
    cokingCapacityDatasource = models.JSONField(null=True, blank=True, default=list)
    pelletizingPlantCapacityQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GT_LT_CHOICES, null=True, blank=True)
    pelletizingPlantCapacity = models.IntegerField(null=True, blank=True)
    pelletizingPlantCapacityDatasource = models.JSONField(null=True, blank=True, default=list)
	
    steelProductCategory = models.JSONField(null=True, blank=True, default=list)
    steelProductCategoryDatasource = models.JSONField(null=True, blank=True, default=list)

    steelProduct = models.JSONField(null=True, blank=True, default=list)
    steelProductDatasource = models.JSONField(null=True, blank=True, default=list)

    stainlessSteel = models.BooleanField(null=True, blank=True)

    endUsers = models.JSONField(null=True, blank=True, default=list)
    endUsersDatasource = models.JSONField(null=True, blank=True, default=list)

    workforceSize = models.IntegerField(null=True, blank=True)
    workforceSizeDatasource = models.JSONField(null=True, blank=True, default=list)

    ISO14001Qualifier = models.TextField(choices=NOT_FOUND_YES_CHOICES, null=True, blank=True)
    ISO14001Day = models.IntegerField(null=True, blank=True)
    ISO14001Month = models.IntegerField(null=True, blank=True)
    ISO14001Year = models.IntegerField(null=True, blank=True)
    ISO14001Datasource = models.JSONField(null=True, blank=True, default=list)
    ISO50001Qualifier = models.TextField(choices=NOT_FOUND_YES_CHOICES, null=True, blank=True)
    ISO50001Day = models.IntegerField(null=True, blank=True)
    ISO50001Month = models.IntegerField(null=True, blank=True)
    ISO50001Year = models.IntegerField(null=True, blank=True)
    ISO50001Datasource = models.JSONField(null=True, blank=True, default=list)
    responsibleSteelQualifier = models.TextField(choices=NOT_FOUND_YES_CHOICES, null=True, blank=True)
    responsibleSteelDay = models.IntegerField(null=True, blank=True)
    responsibleSteelMonth = models.IntegerField(null=True, blank=True)
    responsibleSteelYear = models.IntegerField(null=True, blank=True)
    responsibleSteelDatasource = models.JSONField(null=True, blank=True, default=list)
	
    auxiliaryProductionEquipment = models.TextField(null=True, blank=True)
    auxiliaryProductionEquipmentDatasource = models.JSONField(null=True, blank=True, default=list)
    powerSource = models.TextField(null=True, blank=True)
    powerSourceDatasource = models.JSONField(null=True, blank=True, default=list)
    ironOreSource = models.TextField(null=True, blank=True)
    ironOreSourceDatasource = models.JSONField(null=True, blank=True, default=list)
    metCoalSource = models.TextField(null=True, blank=True)
    metCoalSourceDatasource = models.JSONField(null=True, blank=True, default=list)
    ESJIssues = models.TextField(null=True, blank=True)
    ESJIssuesDatasource = models.JSONField(null=True, blank=True, default=list)


@lru_cache(maxsize=1)
def get_steel_project_fields():
    fields = {}
    for field in SteelProject._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    return fields
 

STEEL_UNIT_TYPE = [
    ('Steel EAF', 'Steel EAF'),
    ('Steel BOF', 'Steel BOF'),
    ('Steel OHF', 'Steel OHF'),
    ('Steel IF', 'Steel IF'),
    ('Steel other/unspecified', 'Steel other/unspecified'),
    ('Iron BF', 'Iron BF'),
    ('Iron DRI', 'Iron DRI'),
    ('Iron other/unspecified', 'Iron other/unspecified'),
]

STEEL_TECHNOLOGY = [
    ("CONARC", "steel"),
    ("unknown/other", "steel"),
    ("Corex", "iron"),
    ("Finex", "iron"),
    ("HIsmelt", "iron"),
    ("HIsarna", "iron"),
    ("Tecnored", "iron"),
    ("electrowinning", "iron"),
    ("unknown/other", "iron"),
]

CALCULATION_METHOD = [
    ("Only unit (total capacity)", "Only unit (total capacity)"),
    ("Allocated total capacity by furnace size", "Allocated total capacity by furnace size"),
    ("Unit-level verified in source", "Unit-level verified in source"),
    ("Assumed equal capacity for each unit at the plant, size unknown", "Assumed equal capacity for each unit at the plant, size unknown"),
    ("Unknown capacity", "Unknown capacity"),
    ("Unknown # of units", "Unknown # of units"),
    ("Calculated from conversion chart", "Calculated from conversion chart"),
]

#shaft furnace; fluidized bed; rotary kiln; hearth; not found

DRI_FURNACE_TYPE = [
    ('shaft furnace', 'shaft furnace'),
    ('fluidized bed', 'fluidized bed'),
    ('rotary kiln', 'rotary kiln'),
    ('hearth', 'hearth'),
    ('not found', 'not found'),
]

# biomass; coal; hydrogen; natural gas; syngas (reformed methane); syngas (gasified coal); waste gas recovery (coke oven gas); waste gas recovery (other); not found

REDUCTANT_TYPE = [
    ('gas', 'gas'), 
    ('coal (solid)', 'coal (solid)'),
    ('biomass (solid)', 'biomass (solid)'), 
    ('unknown', 'unknown')
]

GAS_REDUCTANT = [
    ('syngas (reformed methane)', 'syngas (reformed methane)'), 
    ('syngas (gasified coal)', 'syngas (gasified coal)'), 
    ('syngas (biomass)', 'syngas (biomass)'), 
    ('fossil gas (unreformed)', 'fossil gas (unreformed)'), 
    ('waste gas recovery (coke oven)', 'waste gas recovery (coke oven)'), 
    ('waste gas recovery (other)', 'waste gas recovery (other)'), 
    ('hydrogen', 'hydrogen'), 
    ('gas (unknown type)', 'gas (unknown type)') # empty for now
]

REDUCTANT = [
    ('biomass', 'biomass'), # map to 'biomass (solid)'
    ('coal', 'coal'), # map to coal  ;,
    ('hydrogen', 'hydrogen'), # map to 'gas', 'hydrogen'
    ('methane', 'methane'), # map to 'gas' 'syngas (reformed methane)'
    ('syngas (reformed methane)', 'syngas (reformed methane)'), # map to 'gas' 'syngas (reformed methane)'
    ('syngas (gasified coal)', 'syngas (gasified coal)'), # map to 'gas' 'syngas (gasified coal)'
    ('waste gas recovery (coke oven gas)', 'waste gas recovery (coke oven gas)'), # map to 'gas' 'waste gas recovery (coke oven)'
    ('waste gas recovery (other)', 'waste gas recovery (other)'), # map to 'gas' 'waste gas recovery' (other)'
    ('not found', 'not found'), # map to 'unknown' ?
]

REDUCTANT_COLOR = [
    ('green', 'green'),
    ('blue', 'blue'),
    ('gray', 'gray'),
    ('black', 'black'),
    ('pink', 'pink'),
    ('turquoise', 'turquoise'),
    ('yellow', 'yellow'),
    ('white', 'white'),
    ('not found', 'not found'),
]

REDUCTANT_STATUS = [
    ('capable', 'capable'),
    ('incapable', 'incapable'),
    # ('in-use', 'in-use'), # remove
    # ('not found', 'not found'),  # map to 'unknown'?
    ('unknown', 'unknown'),  # map to 'unknown'?
]

class SteelUnit(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'steel_unit'
    
    unit = models.OneToOneField(PowerUnit, on_delete=models.CASCADE)

    steelTechnology = models.TextField(choices=STEEL_TECHNOLOGY, null=True, blank=True)

    unitType = models.TextField(choices=STEEL_UNIT_TYPE, null=True, blank=True)

    unitNotes = models.TextField(null=True, blank=True)
    capacity = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)

    announcedDay = models.IntegerField(null=True, blank=True)
    announcedMonth = models.IntegerField(null=True, blank=True)
    announcedYear = models.IntegerField(null=True, blank=True)
    announcedDateDatasource = models.JSONField(null=True, blank=True, default=list)
    constructionDay = models.IntegerField(null=True, blank=True)
    constructionMonth = models.IntegerField(null=True, blank=True)
    constructionYear = models.IntegerField(null=True, blank=True)
    constructionDateDatasource = models.JSONField(null=True, blank=True, default=list)
    startDay = models.IntegerField(null=True, blank=True)
    startMonth = models.IntegerField(null=True, blank=True)
    startYear = models.IntegerField(null=True, blank=True)
    startDateDatasource = models.JSONField(null=True, blank=True, default=list)
    preretireAnnouncedDay = models.IntegerField(null=True, blank=True)
    preretireAnnouncedMonth = models.IntegerField(null=True, blank=True)
    preretireAnnouncedYear = models.IntegerField(null=True, blank=True)
    preretireAnnouncedDateDatasource = models.JSONField(null=True, blank=True, default=list)
    idledDay = models.IntegerField(null=True, blank=True)
    idledMonth = models.IntegerField(null=True, blank=True)
    idledYear = models.IntegerField(null=True, blank=True)
    idledDateDatasource = models.JSONField(null=True, blank=True, default=list)
    retiredDay = models.IntegerField(null=True, blank=True)
    retiredMonth = models.IntegerField(null=True, blank=True)
    retiredYear = models.IntegerField(null=True, blank=True)
    retiredDateDatasource = models.JSONField(null=True, blank=True, default=list)
	
    calculationMethod = models.TextField(choices=CALCULATION_METHOD, null=True, blank=True)
    furnaceSize = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    furnaceSizeUnit = models.TextField(null=True, blank=True, choices=FURNACE_SIZE_UNIT_CHOICES)
    furnaceSizeDatasource = models.JSONField(null=True, blank=True, default=list)
	
    furnaceManufacturer = models.TextField(null=True, blank=True)
    furnaceManufacturerDatasource = models.JSONField(null=True, blank=True, default=list)
    furnaceModel = models.TextField(null=True, blank=True)
    furnaceModelDatasource = models.JSONField(null=True, blank=True, default=list)

    scrapBased = models.TextField(null=True, blank=True, choices=NOT_FOUND_YES_N0_CHOICES)
    scrapBasedDatasource = models.JSONField(null=True, blank=True, default=list)

    percentScrapQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    percentScrap =  models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    percentScrapDatasource = models.JSONField(null=True, blank=True, default=list)
    
    percentDRIQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    percentDRI =  models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    percentHBIQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    percentHBI =  models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    percentSpongeIronQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    percentSpongeIron =  models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    DRIHBISource = models.TextField(null=True, blank=True)
    percentBasicPigIronQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    percentBasicPigIron =  models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    percentGranulatedPigIronQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    percentGranulatedPigIron =  models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    percentPigIronQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    percentPigIron =  models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    percentOtherIronQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    percentOtherIron =  models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    percentDatasource = models.JSONField(null=True, blank=True, default=list)

    granularity = models.TextField(null=True, blank=True, choices=GRANULARITY_CHOICES)

    carbonCapture = models.TextField(null=True, blank=True)
    carbonCaptureDatasource = models.JSONField(null=True, blank=True, default=list)
    decarbonizationTechnology = models.TextField(null=True, blank=True)
    decarbonizationTechnologyDatasource = models.JSONField(null=True, blank=True, default=list)

    DRIFurnaceType = models.TextField(choices=DRI_FURNACE_TYPE, null=True, blank=True)
    DRIFurnaceTypeDatasource = models.JSONField(null=True, blank=True, default=list)

    reductant = models.TextField(choices=REDUCTANT, null=True, blank=True)

    reductantType = models.TextField(choices=REDUCTANT_TYPE, null=True, blank=True)
    gasReductant = models.TextField(choices=GAS_REDUCTANT, null=True, blank=True)
    hydrogenReductantConversionAnnounced = models.BooleanField(null=True, blank=True)

    reductantDatasource = models.JSONField(null=True, blank=True, default=list)
    currentHydrogenReductantColor = models.TextField(choices=REDUCTANT_COLOR, null=True, blank=True)
    currentHydrogenReductantColorDatasource = models.JSONField(null=True, blank=True, default=list)
    hydrogenReductantStatus = models.TextField(choices=REDUCTANT_STATUS, null=True, blank=True)
    hydrogenReductantStatusDatasource = models.JSONField(null=True, blank=True, default=list)
    hydrogenReductantConversionDay = models.IntegerField(null=True, blank=True)
    hydrogenReductantConversionMonth = models.IntegerField(null=True, blank=True)
    hydrogenReductantConversionYear = models.IntegerField(null=True, blank=True)
    hydrogenReductantConversionDatasource = models.JSONField(null=True, blank=True, default=list)
    futureHydrogenReductantColor = models.TextField(choices=REDUCTANT_COLOR, null=True, blank=True)
    futureHydrogenReductantColorDatasource = models.JSONField(null=True, blank=True, default=list)
    furnaceHeight = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    furnaceDiameter = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    furnaceVolumeType = models.TextField(null=True, blank=True, choices=FURNACE_VOLUME_TYPE)

@lru_cache(maxsize=1)
def get_steel_unit_fields():
    fields = {}
    for field in SteelUnit._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    return fields


class ReliningCostUnit(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'relining_cost_unit'
    
    option = models.TextField()


FULL_PARTIAL_UNKNOWN = [
    ('full', 'Full'),
    ('partial', 'Partial'),
    ('NF', 'Not found'),
]
	
EXPANSION_UNIT = [
    ('ttpa', 'ttpa'),
    ('m', 'm'),
    ('m3', 'm³'),
    ('%', '%'),
    ('NF', 'Not found'),
]

RELINING_STATUS = [
    ('complete', 'Complete'),
    ('in progress', 'In progress'),
    ('planned', 'Planned'),
    ('cancelled', 'Cancelled'),
    ('not found', 'Not found'),
]

	
class ReliningDetails(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'relining_details'
    
    unit = models.ForeignKey(PowerUnit, on_delete=models.CASCADE, null=True)

    reliningStatus = models.TextField(null=True, blank=True, choices=RELINING_STATUS)
    reliningStatusDatasource = models.JSONField(null=True, blank=True, default=list)
    reliningFullPartial = models.TextField(null=True, blank=True, choices=FULL_PARTIAL_UNKNOWN)
    reliningStartDay = models.IntegerField(null=True, blank=True)
    reliningStartMonth = models.IntegerField(null=True, blank=True)
    reliningStartYear = models.IntegerField(null=True, blank=True)
    reliningStopDay = models.IntegerField(null=True, blank=True)
    reliningStopMonth = models.IntegerField(null=True, blank=True)
    reliningStopYear = models.IntegerField(null=True, blank=True)
    reliningDuration = models.IntegerField(null=True, blank=True)
    reliningNumber = models.IntegerField(null=True, blank=True)
    reliningCost = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)

    reliningCostUnit = models.ForeignKey(ReliningCostUnit, on_delete=models.CASCADE, null=True, blank=True)

    reliningInvestmentDay = models.IntegerField(null=True, blank=True)
    reliningInvestmentMonth = models.IntegerField(null=True, blank=True)
    reliningInvestmentYear = models.IntegerField(null=True, blank=True)
    reliningCapacityExpansion = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    reliningCapacityExpansionUnit = models.TextField(null=True, blank=True, choices=EXPANSION_UNIT)

    reliningDatasource = models.JSONField(null=True, blank=True, default=list)


@lru_cache(maxsize=1)
def get_relining_fields():
    fields = {}
    for field in ReliningDetails._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    return fields


class SteelYearlyProduction(models.Model):
    codelist_table = False

    class Meta:
        db_table = 'steel_yearly_production'
    
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE)
    year = models.IntegerField(null=True, blank=True)
    productionDatasource = models.JSONField(null=True, blank=True, default=list)

    #totalSteelProductionQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    totalSteelProduction = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)

    otherSteelProductionQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    otherSteelProduction = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)

    BOFSteelProdQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    BOFSteelProd = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    EAFSteelProdQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    EAFSteelProd = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    OHFSteelProdQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    OHFSteelProd = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    IFSteelProdQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    IFSteelProd = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)



@lru_cache(maxsize=1)
def get_steel_yearly_production_fields():
    fields = {}
    for field in SteelYearlyProduction._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    return fields


class IronYearlyProduction(models.Model):
    codelist_table = False

    class Meta:
        db_table = 'iron_yearly_production'
    
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE)
    year = models.IntegerField(null=True, blank=True)
    productionDatasource = models.JSONField(null=True, blank=True, default=list)

    #totalIronProductionQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    totalIronProduction = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)

    otherIronProductionQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    otherIronProduction = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)

    BFIronProdQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    BFIronProd = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    DRIIronProdQualifier = models.CharField(max_length=2, choices=NOT_FOUND_GREATER_THAN_ZERO, null=True, blank=True)
    DRIIronProd = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)


@lru_cache(maxsize=1)
def get_iron_yearly_production_fields():
    fields = {}
    for field in IronYearlyProduction._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    return fields

YES_NO_BLANK_CHOICES = [
    ('', ''),
    ('yes', 'yes'),
]

CAPACITY_UNIT_CHOICES = [
    ('bcf/d', 'bcf/d'),
    ('MWh/d', 'MWh/d'),
    ('mtpa', 'mtpa'),
    ('tpa', 'tpa'),
    ('bcm/y', 'bcm/y'),
    ('TJ/d', 'TJ/d'),
    ('bpd', 'bpd'),
    ('gal/day', 'gal/day'),
    ('MMcf/d', 'MMcf/d'),
]


COST_UNIT_CHOICES = [
    ('SWE', 'SWE'),
    ('RUB', 'RUB'),
    ('RMB', 'RMB'),
    ('LTL', 'LTL'),
    ('GBP', 'GBP'),
    ('HKD', 'HKD'),
    ('BRL', 'BRL'),
    ('NTD', 'NTD'),
    ('USD', 'USD'),
    ('CAN', 'CAN'),
    ('THB', 'THB'),
    ('EUR', 'EUR'),
    ('AUD', 'AUD'),
    ('PHP', 'PHP'),
    ('KRW', 'KRW'),
    ('MR', 'MR'),
    ('INR', 'INR'),
    ('YEN', 'YEN'),
]


class LNGProject(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'lng_project'
    
    project = models.OneToOneField(Plant, on_delete=models.CASCADE)

    capacity = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    capacityUnit = models.TextField(null=True, blank=True, choices=CAPACITY_UNIT_CHOICES)
    capacityDatasource = models.JSONField(null=True, blank=True, default=list)
    cost = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    costUnit = models.TextField(null=True, blank=True, choices=COST_UNIT_CHOICES)
    costYear = models.IntegerField(null=True, blank=True)
    costDatasource = models.JSONField(null=True, blank=True, default=list)
    financing = models.TextField(null=True, blank=True)
    financingDatasource = models.JSONField(null=True, blank=True, default=list)

    associatedProjects = models.JSONField(null=True, blank=True, default=list)
    associatedProjectsDatasource = models.JSONField(null=True, blank=True, default=list)

    LNGSource = models.JSONField(null=True, blank=True, default=list)
    LNGSourceDatasource = models.JSONField(null=True, blank=True, default=list)
    powerPlantsSupplied = models.JSONField(null=True, blank=True, default=list)
    powerPlantsSuppliedDatasource = models.JSONField(null=True, blank=True, default=list)
    captiveGasPower = models.BooleanField(null=True, blank=True)
    captiveGasPowerDatasource = models.JSONField(null=True, blank=True, default=list)
    pipelines = models.JSONField(null=True, blank=True, default=list)
    pipelinesDatasource = models.JSONField(null=True, blank=True, default=list)
    pciNotes = models.TextField(null=True, blank=True)
    pci3 = models.TextField(choices=YES_NO_BLANK_CHOICES, null=True, blank=True)
    pci4 = models.TextField(choices=YES_NO_BLANK_CHOICES, null=True, blank=True)
    pci5 = models.TextField(choices=YES_NO_BLANK_CHOICES, null=True, blank=True)
    pci6 = models.TextField(choices=YES_NO_BLANK_CHOICES, null=True, blank=True)
    offshore = models.BooleanField(null=True, blank=True)
    floating = models.BooleanField(null=True, blank=True)
    vesselName = models.JSONField(null=True, blank=True, default=list)
    vesselNameDatasource = models.JSONField(null=True, blank=True, default=list)

    opposition = models.BooleanField(null=True, blank=True)
    oppositionDatasource = models.JSONField(null=True, blank=True, default=list)

    oppositionNotes = models.TextField(null=True, blank=True)

    esjNotes = models.TextField(null=True, blank=True)

    ccs = models.BooleanField(null=True, blank=True)
    ccsDatasource = models.JSONField(null=True, blank=True, default=list)
    ccsNotes = models.TextField(null=True, blank=True)

@lru_cache(maxsize=1)
def get_lng_project_fields():
    fields = {}
    for field in LNGProject._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    return fields


LNG_FUEL_CHOICES = [
    ('LNG', 'LNG'),
    ('Oil+NGL', 'Oil+NGL'),
    ('NGL', 'NGL'),
    ('Oil', 'Oil'),
    ('Oil+Fuels', 'Oil+Fuels'),
    ('LH2', 'LH2'),
    ('NH3', 'NH3'),
    ('eLNG', 'eLNG'),
]

FACILITY_TYPE_CHOICES = [
    ('import', 'import'),
    ('export', 'export'),
]

TEMP_FACILITY_CHOICES = [
    ('interim facility', 'interim facility'),
    ('permanent replacement', 'permanent replacement'),
]

FID_STATUS_CHOICES = [
    ('Pre-FID', 'Pre-FID'),
    ('FID', 'FID'),
]

TRAIN_NUMBERS = [('', '')] + [(str(i), str(i)) for i in range(1, 51)]

class LNGUnit(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'lng_unit'

    unit = models.OneToOneField(PowerUnit, on_delete=models.CASCADE)
    fuel = models.TextField(null=True, blank=True, choices=LNG_FUEL_CHOICES)
    facilityType = models.TextField(null=True, blank=True, choices=FACILITY_TYPE_CHOICES)
    facilityTypeDatasource = models.JSONField(null=True, blank=True, default=list)
    trains = models.TextField(null=True, blank=True, choices=TRAIN_NUMBERS)
    capacity = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    capacityUnit = models.TextField(null=True, blank=True, choices=CAPACITY_UNIT_CHOICES)
    researcherNotes = models.TextField(null=True, blank=True)
    cost = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    costUnit = models.TextField(null=True, blank=True)
    costYear = models.IntegerField(null=True, blank=True)
    costDatasource = models.JSONField(null=True, blank=True, default=list)
    financing = models.TextField(null=True, blank=True)
    financingDatasource = models.JSONField(null=True, blank=True, default=list)
    tempFacility = models.TextField(null=True, blank=True, choices=TEMP_FACILITY_CHOICES)
    importExportOnly = models.BooleanField(null=True, blank=True)
    fidStatus = models.TextField(null=True, blank=True, choices=FID_STATUS_CHOICES)
    fidYear = models.IntegerField(null=True, blank=True)
    fidDatasource = models.JSONField(null=True, blank=True, default=list)
    defeated = models.BooleanField(null=True, blank=True)
    defeatedDatasource = models.JSONField(null=True, blank=True, default=list)
    LH2 = models.BooleanField(null=True, blank=True)
    NH3 = models.BooleanField(null=True, blank=True)
    syntheticLNG = models.BooleanField(null=True, blank=True)
    retrofitProposed = models.BooleanField(null=True, blank=True)
    altFuelDatasource = models.JSONField(null=True, blank=True, default=list)
    altFuelPrelimAgreement = models.BooleanField(null=True, blank=True)
    altFuelPrelimAgreementDatasource = models.JSONField(null=True, blank=True, default=list)
    altFuelCallMarketInterest = models.BooleanField(null=True, blank=True)
    altFuelCallMarketInterestDatasource = models.JSONField(null=True, blank=True, default=list)
    altFuelNotes = models.TextField(null=True, blank=True)


@lru_cache(maxsize=1)
def get_lng_unit_fields():
    fields = {}
    for field in LNGUnit._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    return fields


OFFSHORE_CHOICES = [
    ('unknown', 'unknown'),
    ('offshore', 'offshore'),
    ('onshore', 'onshore'),
]

PRODUCTION_TYPE_CHOICES = [
    ('', ''),
    ('conventional', 'conventional'),
    ('unconventional', 'unconventional'),
]

#oil and gas; oil; gas

FUEL_TYPE_CHOICES = [
    ('', ''),
    ('oil', 'oil'),
    ('gas', 'gas'),
    ('oil and gas', 'oil and gas'),
    ('gas and condensate', 'gas and condensate'),
    ('gas; ngl', 'gas; ngl'),
]

#field; project; block; concession; complex; basin; area; pool; sub-basin; asset; phase
UNIT_TYPE_CHOICES = [
    ('', ''),
    ('field', 'field'),
    ('project', 'project'),
    ('block', 'block'),
    ('concession', 'concession'),
    ('pool', 'pool'),
    ('asset', 'asset'),
    ('phase', 'phase'),
]


class GOGETProject(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'goget_project'

    namePrefix = models.TextField(null=True, blank=True)
    
    project = models.OneToOneField(Plant, on_delete=models.CASCADE)

    makeWIKI = models.BooleanField(null=True, blank=True)

    basin = models.TextField(null=True, blank=True)

    basinDatasource = models.JSONField(null=True, blank=True, default=list)
    
    concessionBlock = models.TextField(null=True, blank=True)
    concessionBlock2 = models.TextField(null=True, blank=True)
    concessionBlock3 = models.TextField(null=True, blank=True)
    concessionBlock4 = models.TextField(null=True, blank=True)
    concessionBlock5 = models.TextField(null=True, blank=True)
    concessionBlock6 = models.TextField(null=True, blank=True)
    concessionBlock7 = models.TextField(null=True, blank=True)

    concessionBlockDatasource = models.JSONField(null=True, blank=True, default=list)

    projectComplex = models.ForeignKey(
        Plant,
        related_name='+',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    projectComplexDatasource = models.JSONField(null=True, blank=True, default=list)

    offshore = models.TextField(null=True, blank=True, choices=OFFSHORE_CHOICES)

    offshoreDatasource = models.JSONField(null=True, blank=True, default=list)

    productionType = models.TextField(null=True, blank=True, choices=PRODUCTION_TYPE_CHOICES)

    productionTypeDatasource = models.JSONField(null=True, blank=True, default=list)

    fuelType = models.TextField(null=True, blank=True, choices=FUEL_TYPE_CHOICES)

    unitType = models.TextField(null=True, blank=True, choices=UNIT_TYPE_CHOICES)

    capex = models.BigIntegerField(null=True, blank=True)
    capexDatasource = models.JSONField(null=True, blank=True, default=list)

# fuelType
# unitType

@lru_cache(maxsize=1)
def get_goget_project_fields():
    fields = {}
    for field in GOGETProject._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    
    return fields


class ReserveClassification(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'reserve_type'
    name = models.TextField(null=True, unique=True)

class QuantityUnit(models.Model):
    codelist_table = True
    class Meta:
        db_table = 'quantity_unit'
    name = models.TextField(null=True, unique=True)
    production_reserves = models.TextField(null=True, blank=True, choices=(('production', 'production'), ('reserves', 'reserves')))
    description = models.TextField(null=True, blank=True)
    unit = models.TextField(null=True, blank=True)
    common_unit = models.TextField(null=True, blank=True)
    conversion_factor = models.DecimalField(max_digits=25, decimal_places=15, null=True, blank=True)


PRODUCTION_RESERVES_CHOICES = [
    ('reserves', 'reserves'),
    ('cumulative production', 'cumulative production'),
    ('production', 'production'),
    ('production design capacity', 'production design capacity'),
]


FUEL_DESC_CHOICES = [
    ('', ''),
    ('[not stated]', '[not stated]'),
    ('associated gas', 'associated gas'),
    ('coal bed methane', 'coal bed methane'),
    ('coal seam gas', 'coal seam gas'),
    ('condensate', 'condensate'),
    ('condensate and LPG', 'condensate and LPG'),
    ('crude oil', 'crude oil'),
    ('crude oil and condensate', 'crude oil and condensate'),
    ('dry gas', 'dry gas'),
    ('gas', 'gas'),
    ('gas and condensate', 'gas and condensate'),
    ('gas condensate', 'gas condensate'),
    ('hydrocarbons', 'hydrocarbons'),
    ('liquid hydrocarbons', 'liquid hydrocarbons'),
    ('liquids', 'liquids'),
    ('LNG', 'LNG'),
    ('LPG', 'LPG'),
    ('NGL', 'NGL'),
    ('Non-associated gas', 'Non-associated gas'),
    ('nonassociated gas', 'nonassociated gas'),
    ('oil', 'oil'),
    ('oil and associated gas', 'oil and associated gas'),
    ('oil and condensate', 'oil and condensate'),
    ('oil and gas', 'oil and gas'),
    ('oil and gas condensate', 'oil and gas condensate'),
    ('oil and LPG', 'oil and LPG'),
    ('oil and NGL', 'oil and NGL'),
    ('oil, NGL, and gas', 'oil, NGL, and gas'),
    ('sales gas', 'sales gas'),
    ('total liquids', 'total liquids'),
]

GOGET_QUANTITY_UNITS = [
    'thousand bbl',
    'million cubic feet',
    'thousand m³/d',
    'thousand cubic feet',
    'million SCF/d',
    'metric tons/d',
    'bcf/d',
    'million boe',
    'million scf/d',
    'thousand cubic feet/y',
    'thousand tons/y',
    'tons',
    'million metric standard m³/y',
    'million metric tons',
    'tonnes/y',
    'kL',
    'STB/d',
    'kilotonnes/y',
    'petajoules',
    'billion bbl',
    'million stock tank barrels',
    'm³/y',
    'thousand m³/y',
    'million toe/y',
    'thousand metric tons/y',
    'thousand tons',
    'thousand Sm³/d',
    'Sm³/d',
    'billion Nm³',
    'million tonnes/y',
    'tonnes/d',
    'thousand Sm³/y',
    'billion Sm³/y',
    'million Nm³/d',
    'boe',
    'bbl',
    'boe/y',
    'thousand tonnes/d',
    'million cubic feet/y',
    'GNm³ (Groningen normal cubic meters)',
    'bcm',
    'million Sm³/d',
    'thousand bbl/y',
    'million toe',
    'tj/d',
    'million cubic feet/d',
    'm³',
    'thousand tonnes/y',
    'million m³/d',
    'Nm³',
    'trillion m³',
    'kscm/d',
    'tcf/y',
    'million boe/y',
    'million bbl/y',
    'billion scf',
    'bpd',
    'm³/d',
    'million bbl/d',
    'million tons',
    'bcf/y',
    'billion scf/y',
    'megalitres',
    'million metric tons/y',
    'billion SCF',
    'million tons/d',
    'million Sm³ o.e.',
    'bcm/y',
    'tons/d',
    'billion cubic feet',
    'billion m³',
    'giga m³',
    'million scf',
    'million metric tonnes',
    'cubic feet/d',
    'petajoules/y',
    'million bbl',
    'boe/d',
    'million m³/y',
    'thousand boe/d',
    'million cubic meters',
    'tscf',
    'billion tons',
    'million Nm³',
    'thousand scf/d',
    'm³(Vn)',
    'million Nm³/y',
    'million scf/y',
    'thousand m³',
    'billion tonnes',
    'trillion cubic feet',
    'billion Sm³',
    'thousand Sm³',
    'thousand toe/y',
    'metric tons',
    'million boe/d',
    'tcf',
    'bbl/d',
    'thousand tonnes',
    'million metric tonnes/y',
    'thousand cubic feet/d',
    'scf',
    'thousand toe',
    'million barrels',
    'bcf',
    'MMscfd (million standard cubic feet per day)',
    'billion boe',
    'tonnes',
    'billion Nm³/y',
    'thousand scf',
    'billion scf/d',
    'million m³',
    'million Sm³/y',
    'bbl/y',
    'million metric standard m³',
    'giga m³/y',
    'thousand bbl/d',
    'million cubic meters/d',
    'million Sm³',
    'million cubic meters/y',
    'thousand scf/y',
    'megalitres/y',
    'tons/y',
    'billion metric tons',
    'million standard cubic meters per day',
    'million tonnes',
    'million tons/y',
    'm³(Vn)/y',
    'giga cubic feet',
    'Sm³/y',
    'thousand boe',
    'bopd',
    '42-gallon barrels/d',
    'thousand 42-gallon barrels/y'
]


GOGET_QUANTITY_UNIT_CHOICES = [(unit, unit) for unit in GOGET_QUANTITY_UNITS]


class ReservesProduction(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'reserves_production'
    
    project = models.ForeignKey(Plant, on_delete=models.CASCADE, null=False)

    productionReserves = models.TextField(null=True, blank=True, choices=PRODUCTION_RESERVES_CHOICES)

    fuelDesc = models.TextField(null=True, blank=True, choices=FUEL_DESC_CHOICES)

    reserveClassification = models.TextField(null=True, blank=True)

    quantity = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    quantityUnit = models.TextField(null=True, blank=True, choices=GOGET_QUANTITY_UNIT_CHOICES)

    year = models.IntegerField(null=True, blank=True)

    reserveProductionDatasource = models.JSONField(null=True, blank=True, default=list)

    notes = models.TextField(null=True, blank=True)


@lru_cache(maxsize=1)
def get_reserves_production_fields():
    fields = {}
    for field in ReservesProduction._meta.fields:
        if field.name in ['id']:
            continue
        if field.related_model is not None:
            name = f'{field.name}_id'
            fields[name] = field.get_internal_type()
        else:
            fields[field.name] = field.get_internal_type()
    return fields


class ProjectGeospatial(models.Model):
    codelist_table = False
    class Meta:
        db_table = 'project_geospatial'
    
    project = models.ForeignKey(Plant, on_delete=models.CASCADE, null=False)
    wkt = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.project.name} - {self.wkt}"
