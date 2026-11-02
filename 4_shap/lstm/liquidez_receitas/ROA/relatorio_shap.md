# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_receitas/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_receitas/ROA/preprocessadores_ROA.joblib`
- Target: `ROA`
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
    1 receitas_de_intermediacao_financeira_sobre_ativo_total                0.001056                        0.000719                -0.000097
    2                                            crise_covid                0.000952                        0.000617                 0.000573
    3          rendas_de_operacoes_com_TVM_sobre_ativo_total                0.000943                        0.000609                -0.000218
    4      rendas_de_prestacao_de_servicos_sobre_ativo_total                0.000688                        0.000286                 0.000014
    5          rendas_de_tarifas_bancarias_sobre_ativo_total                0.000521                        0.000293                 0.000071
    6                                              crise_nme                0.000495                        0.000403                 0.000402
    7                            captacoes_sobre_ativo_total                0.000410                        0.000391                -0.000165
    8                    depositos_a_prazo_sobre_ativo_total                0.000345                        0.000297                 0.000023
    9                                      liquidez_imediata                0.000343                        0.000231                 0.000045
   10                                 indice_de_imobilizacao                0.000333                        0.000170                 0.000034
   11                    depositos_a_vista_sobre_ativo_total                0.000309                        0.000279                -0.000002
   12                   operacoes_de_credito_sobre_captacoes                0.000303                        0.000164                -0.000061
   13                                                estatal                0.000295                        0.000249                -0.000039
   14                       disponibilidades_sobre_depositos                0.000243                        0.000101                 0.000055
   15                                                lcr_dec                0.000188                        0.000124                 0.000040
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-7                    0.002495               -0.000085
    2   t                    0.001426                0.000186
    3 t-6                    0.001156                0.000212
    4 t-5                    0.000632                0.000163
    5 t-4                    0.000591                0.000065
    6 t-1                    0.000548                0.000066
    7 t-2                    0.000509                0.000021
    8 t-3                    0.000499                0.000105
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

Tempo total de execução: 584.52 segundos.