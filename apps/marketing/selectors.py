"""Marketing read queries (docs §15.1, §10.5 lead counts)."""
from django.db.models import Count

from .constants import CAMPAIGNTYPE_TO_FE, FE_TO_CHANNEL, ChannelType
from .models import (
    Campaign,
    CampaignSelectedType,
    EventRecord,
    ExhibitionRecord,
    SocialMediaAdRecord,
    SocialPlatformDefinition,
    StreetAdRecord,
    TVAdRecord,
)

_CHANNEL_MODEL = {
    ChannelType.EVENT: EventRecord,
    ChannelType.TV_AD: TVAdRecord,
    ChannelType.STREET_AD: StreetAdRecord,
    ChannelType.EXHIBITION: ExhibitionRecord,
    ChannelType.SOCIAL_MEDIA_AD: SocialMediaAdRecord,
}


def campaigns_for_company(company):
    return (
        Campaign.objects.filter(company=company)
        .select_related("created_by")
        .prefetch_related("selected_types")
        .annotate(lead_count=Count("lead_attributions"))
        .order_by("-created_at")
    )


def campaigns_for_user(user, company):
    from apps.authorization.services import EffectivePermissionResolver

    qs = campaigns_for_company(company)
    if EffectivePermissionResolver.has(user, "marketing.campaign.view_all"):
        return qs
    return qs.filter(created_by=user)


def active_campaigns(company):
    """Campaigns usable as a lead source (approved + not archived)."""
    return (
        Campaign.objects.filter(company=company, archived_at__isnull=True)
        .order_by("name")
    )


def campaign_available_channels(campaign):
    """Frontend channels this campaign actually selected (docs §10). Only these
    appear in the channel picker — e.g. an events-only campaign won't offer
    Social Media."""
    codes = CampaignSelectedType.objects.filter(campaign=campaign).values_list(
        "type_code", flat=True
    )
    out = []
    for tc in codes:
        fe = CAMPAIGNTYPE_TO_FE.get(tc)
        if fe:
            out.append({"value": fe, "label": fe.replace("_", " ").title()})
    return out


def channel_records(*, company, fe_channel, campaign=None, platform_id=None):
    """[{id, name}] records for a frontend channel value (docs §10.5). When
    `campaign` is None the records span the whole company (used by Walk-in /
    Call Center / Exhibition capture). For social media, pass platform_id for
    that platform's ads; without it, return the platform list."""
    ct = FE_TO_CHANNEL.get(fe_channel)
    if ct is None:
        return []
    if ct == ChannelType.SOCIAL_MEDIA_AD:
        if not platform_id:
            return [
                {"id": str(p.id), "name": p.name}
                for p in SocialPlatformDefinition.objects.filter(is_active=True)
                .order_by("name")
            ]
        qs = SocialMediaAdRecord.objects.filter(platform_lines__platform_id=platform_id)
        qs = qs.filter(campaign=campaign) if campaign else qs.filter(
            campaign__company=company)
        qs = qs.distinct()
    else:
        model = _CHANNEL_MODEL[ct]
        qs = model.objects.filter(campaign=campaign) if campaign else model.objects.filter(
            campaign__company=company)
    return [{"id": str(o.id), "name": o.name, "campaign_id": str(o.campaign_id)}
            for o in qs.order_by("name")]

