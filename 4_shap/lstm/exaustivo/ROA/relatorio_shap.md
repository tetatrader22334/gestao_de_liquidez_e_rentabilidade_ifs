# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/exaustivo/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/exaustivo/ROA/preprocessadores_ROA.joblib`
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
 rank                                                   feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                                             pib_indice_sa                0.000769                        0.000521                 0.000508
    2                                         pib_indice_sa_log                0.000602                        0.000578                 0.000575
    3                       provisao_sobre_operacoes_de_credito                0.000452                        0.000264                -0.000156
    4                                         depositos_a_vista                0.000451                        0.000253                -0.000154
    5                                      hhi_contribuicao_dec                0.000432                        0.000201                 0.000118
    6         rendas_de_prestacao_de_servicos_sobre_ativo_total                0.000415                        0.000209                 0.000087
    7                                    ativos_sobre_captacoes                0.000367                        0.000337                -0.000036
    8 resultado_de_provisao_para_creditos_de_dificil_liquidacao                0.000350                        0.000140                 0.000036
    9                      despesas_de_intermediacao_financeira                0.000348                        0.000125                -0.000057
   10                                                 depositos                0.000317                        0.000128                -0.000045
   11                               captacoes_sobre_ativo_total                0.000306                        0.000301                -0.000080
   12                           rendas_de_prestacao_de_servicos                0.000285                        0.000136                 0.000032
   13    receitas_de_intermediacao_financeira_sobre_ativo_total                0.000285                        0.000150                -0.000019
   14                            rendas_de_operacoes_de_credito                0.000281                        0.000221                 0.000110
   15                                             passivo_total                0.000275                        0.000212                 0.000124
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.004632                0.000688
    2 t-5                    0.003980                0.000038
    3 t-1                    0.001901                0.000282
    4 t-4                    0.001798                0.000112
    5 t-2                    0.001449                0.000174
    6 t-3                    0.001437                0.000178
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

Tempo total de execução: 244.52 segundos.