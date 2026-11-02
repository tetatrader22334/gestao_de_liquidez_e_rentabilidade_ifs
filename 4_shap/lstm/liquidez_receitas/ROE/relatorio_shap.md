# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_receitas/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_receitas/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `8`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 503
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                                                feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1          rendas_de_operacoes_com_TVM_sobre_ativo_total                0.011218                        0.007278                -0.004125
    2 receitas_de_intermediacao_financeira_sobre_ativo_total                0.010212                        0.006743                -0.001600
    3                                            crise_covid                0.009973                        0.007914                 0.007217
    4          rendas_de_tarifas_bancarias_sobre_ativo_total                0.008803                        0.005494                 0.001562
    5                                                estatal                0.004970                        0.004970                -0.000717
    6                    depositos_a_prazo_sobre_ativo_total                0.004646                        0.003910                -0.000509
    7      rendas_de_prestacao_de_servicos_sobre_ativo_total                0.004526                        0.002773                -0.001439
    8                                              crise_nme                0.004494                        0.003118                 0.003118
    9                                 indice_de_imobilizacao                0.003218                        0.001610                 0.000114
   10                                      liquidez_imediata                0.002730                        0.001819                 0.000663
   11                                                lcr_dec                0.002479                        0.002090                 0.001018
   12                                 ativos_sobre_depositos                0.002089                        0.001231                -0.000830
   13                                               nsfr_dec                0.001719                        0.001671                -0.000178
   14                    depositos_a_vista_sobre_ativo_total                0.001672                        0.001285                -0.000259
   15                   operacoes_de_credito_sobre_captacoes                0.001666                        0.001317                -0.000143
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-7                    0.022622               -0.000460
    2   t                    0.017503               -0.000377
    3 t-5                    0.007036                0.001804
    4 t-1                    0.006838               -0.000006
    5 t-6                    0.006756                0.001175
    6 t-2                    0.006263                0.000171
    7 t-3                    0.006050                0.001148
    8 t-4                    0.005972                0.000590
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

Tempo total de execução: 265.63 segundos.