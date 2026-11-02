# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/geral/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/geral/ROA/preprocessadores_ROA.joblib`
- Target: `ROA`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `6`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 531
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                                                feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                                      pib_indice_sa_log                0.002082                        0.001314                 0.001314
    2                                 ipca_fim_trimestre_dec                0.000763                        0.000502                 0.000328
    3          rendas_de_operacoes_com_TVM_sobre_ativo_total                0.000741                        0.000562                -0.000087
    4                                        hhi_periodo_dec                0.000710                        0.000330                 0.000330
    5                   operacoes_de_credito_sobre_captacoes                0.000651                        0.000319                -0.000054
    6      rendas_de_prestacao_de_servicos_sobre_ativo_total                0.000554                        0.000222                -0.000012
    7 receitas_de_intermediacao_financeira_sobre_ativo_total                0.000536                        0.000465                -0.000058
    8          resultado_de_provisao_pcddl_sobre_ativo_total                0.000369                        0.000213                 0.000011
    9                                            crise_covid                0.000363                        0.000182                 0.000101
   10                  resultado_de_intermediacao_financeira                0.000331                        0.000128                 0.000034
   11                    despesas_de_captacao_sobre_receitas                0.000305                        0.000281                -0.000198
   12                            captacoes_sobre_ativo_total                0.000281                        0.000253                -0.000125
   13                       disponibilidades_sobre_depositos                0.000245                        0.000094                 0.000009
   14                                      liquidez_imediata                0.000225                        0.000162                 0.000123
   15          rendas_de_tarifas_bancarias_sobre_ativo_total                0.000221                        0.000129                 0.000041
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.003710                0.000877
    2 t-5                    0.002830                0.000235
    3 t-4                    0.001318                0.000204
    4 t-3                    0.000844                0.000043
    5 t-2                    0.000726                0.000168
    6 t-1                    0.000697                0.000109
```

## Arquivos gerados
- `shap_values_flat.npy`
- `shap_values_3d.npy`
- `shap_base_values.npy`
- `metadados_amostras_shap.csv`
- `shap_importance_lag_feature.csv`
- `shap_importance_feature_aggregated.csv`
- `shap_importance_by_lag.csv`
- `shap_bar_flat_top.png`
- `shap_beeswarm_flat_top.png`
- `shap_bar_feature_aggregated_top.png`
- `shap_heatmap_feature_lag_top.png`

Tempo total de execução: 107.86 segundos.