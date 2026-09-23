from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.socio import Socio


class PartnerSearchService:
    """Expoe os socios/administradores ja presentes nos dados cadastrais da empresa
    (BrasilAPI). Mantido como um service dedicado para dar um ponto unico de extensao
    caso, no futuro, a busca de socios passe a combinar mais de uma fonte."""

    async def search(self, company: Company) -> list[Socio]:
        return company.socios
