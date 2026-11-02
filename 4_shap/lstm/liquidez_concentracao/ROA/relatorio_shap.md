# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_concentracao/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_concentracao/ROA/preprocessadores_ROA.joblib`
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
    1                          crise_covid                0.000400                        0.000377                 0.000377
    2                      hhi_periodo_dec                0.000339                        0.000278                 0.000278
    3                              estatal                0.000298                        0.000297                -0.000022
    4          captacoes_sobre_ativo_total                0.000274                        0.000273                -0.000082
    5  depositos_a_prazo_sobre_ativo_total                0.000201                        0.000201                -0.000045
    6                    liquidez_imediata                0.000193                        0.000192                -0.000026
    7  depositos_a_vista_sobre_ativo_total                0.000149                        0.000143                 0.000021
    8               indice_de_imobilizacao                0.000117                        0.000100                -0.000053
    9                            crise_nme                0.000114                        0.000113                 0.000113
   10                     market_share_dec                0.000089                        0.000074                -0.000015
   11     disponibilidades_sobre_depositos                0.000082                        0.000049                -0.000019
   12                 controle_estrangeiro                0.000081                        0.000081                 0.000065
   13                             nsfr_dec                0.000071                        0.000048                 0.000007
   14               ativos_sobre_depositos                0.000057                        0.000051                -0.000045
   15 operacoes_de_credito_sobre_captacoes                0.000046                        0.000039                -0.000029
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-7                    0.000423                0.000110
    2 t-6                    0.000361                0.000098
    3   t                    0.000355               -0.000026
    4 t-5                    0.000324                0.000111
    5 t-4                    0.000297                0.000093
    6 t-3                    0.000277                0.000077
    7 t-2                    0.000256                0.000049
    8 t-1                    0.000255                0.000008
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

Tempo total de execução: 114.70 segundos.