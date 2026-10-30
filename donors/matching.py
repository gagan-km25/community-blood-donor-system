"""Preliminary ABO/Rh compatibility helpers.

IMPORTANT: these rules describe *red-cell transfusion compatibility* at a
textbook level. They are only a first filter for finding potential donor leads.
Real transfusion decisions require crossmatching and eligibility screening by
qualified healthcare professionals.
"""

from django.db.models import Q

from .models import BloodGroup, DonorProfile

# Which donor groups can give red cells to which recipient group.
COMPATIBLE_DONORS = {
    BloodGroup.O_NEG: [BloodGroup.O_NEG],
    BloodGroup.O_POS: [BloodGroup.O_POS, BloodGroup.O_NEG],
    BloodGroup.A_NEG: [BloodGroup.A_NEG, BloodGroup.O_NEG],
    BloodGroup.A_POS: [BloodGroup.A_POS, BloodGroup.A_NEG, BloodGroup.O_POS, BloodGroup.O_NEG],
    BloodGroup.B_NEG: [BloodGroup.B_NEG, BloodGroup.O_NEG],
    BloodGroup.B_POS: [BloodGroup.B_POS, BloodGroup.B_NEG, BloodGroup.O_POS, BloodGroup.O_NEG],
    BloodGroup.AB_NEG: [BloodGroup.AB_NEG, BloodGroup.A_NEG, BloodGroup.B_NEG, BloodGroup.O_NEG],
    BloodGroup.AB_POS: list(BloodGroup.values),  # universal recipient
}


def compatible_donor_groups(recipient_group: str) -> list[str]:
    """Return the donor blood groups compatible with a recipient group."""
    return COMPATIBLE_DONORS.get(recipient_group, [])


def recipient_groups_for_donor(donor_group: str) -> list[str]:
    """Inverse lookup: recipient groups a donor of this group could help,
    returned in canonical BloodGroup order."""
    return [
        group for group in BloodGroup.values
        if donor_group in COMPATIBLE_DONORS[group]
    ]


def find_potential_donors(blood_request, limit: int = 20):
    """Return active, available donors that are potential leads for a request.

    Criteria: compatible blood group, city matches the hospital city
    (case-insensitive substring), profile active and marked available.
    This is lead discovery only — it never changes the request status.
    """
    groups = compatible_donor_groups(blood_request.blood_group)
    return (
        DonorProfile.objects
        .filter(is_active=True, is_available=True, blood_group__in=groups)
        .filter(Q(city__icontains=blood_request.hospital_city))
        .select_related('user')
        .order_by('-updated_at')[:limit]
    )
