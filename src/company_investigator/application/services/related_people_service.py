from company_investigator.domain.entities.investigation import EmpresaRelacionada, PessoaRelacionada


class RelatedPeopleService:
    """Agrega as pessoas (socios e pessoas-chave do LinkedIn) ja descobertas pelas
    sub-investigacoes das empresas relacionadas. Nao faz nenhuma busca nova: e uma
    visao consolidada sobre dados que os outros services ja coletaram, evitando
    duplicar logica de descoberta (PartnerSearchService/LinkedInSearchService)."""

    def collect(self, empresas_relacionadas: list[EmpresaRelacionada]) -> list[PessoaRelacionada]:
        vistas: dict[tuple[str, str], PessoaRelacionada] = {}

        for relacionada in empresas_relacionadas:
            nome_empresa = relacionada.empresa.nome_fantasia or relacionada.empresa.razao_social

            for socio in relacionada.investigacao.socios:
                chave = (socio.nome, nome_empresa)
                vistas.setdefault(
                    chave,
                    PessoaRelacionada(
                        nome=socio.nome,
                        papel=socio.qualificacao,
                        empresa_relacionada=nome_empresa,
                        fonte="BrasilAPI",
                        confianca=relacionada.confianca,
                    ),
                )

            for pessoa_chave in relacionada.investigacao.pessoas_chave:
                chave = (pessoa_chave.nome, nome_empresa)
                vistas.setdefault(
                    chave,
                    PessoaRelacionada(
                        nome=pessoa_chave.nome,
                        papel=pessoa_chave.cargo,
                        empresa_relacionada=nome_empresa,
                        fonte="LinkedIn (via SearchProvider)",
                        confianca=pessoa_chave.confianca,
                    ),
                )

        return list(vistas.values())
