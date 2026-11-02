# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_macro/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_macro/ROA/preprocessadores_ROA.joblib`
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
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                    pib_indice_sa_log                0.001112                        0.000979                -0.000927
    2                              estatal                0.000394                        0.000392                -0.000097
    3                          crise_covid                0.000368                        0.000290                 0.000049
    4          captacoes_sobre_ativo_total                0.000358                        0.000323                -0.000139
    5                    liquidez_imediata                0.000317                        0.000291                -0.000055
    6               ipca_fim_trimestre_dec                0.000296                        0.000160                -0.000038
    7               indice_de_imobilizacao                0.000275                        0.000262                 0.000046
    8                 controle_estrangeiro                0.000275                        0.000275                 0.000191
    9              selic_fim_trimestre_dec                0.000272                        0.000186                -0.000095
   10  depositos_a_prazo_sobre_ativo_total                0.000245                        0.000204                -0.000114
   11  depositos_a_vista_sobre_ativo_total                0.000219                        0.000207                 0.000004
   12     disponibilidades_sobre_depositos                0.000192                        0.000179                -0.000109
   13                              lcr_dec                0.000172                        0.000162                -0.000085
   14 operacoes_de_credito_sobre_captacoes                0.000165                        0.000141                -0.000043
   15                            crise_nme                0.000120                        0.000114                 0.000114
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-6                    0.000813               -0.000241
    2 t-5                    0.000792               -0.000255
    3 t-7                    0.000777               -0.000254
    4 t-4                    0.000730               -0.000239
    5 t-3                    0.000636               -0.000186
    6 t-2                    0.000528               -0.000124
    7 t-1                    0.000398               -0.000055
    8   t                    0.000267                0.000035
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

Tempo total de execução: 148.77 segundos.