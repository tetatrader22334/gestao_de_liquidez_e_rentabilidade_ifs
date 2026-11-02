# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_complementar/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_complementar/ROA/preprocessadores_ROA.joblib`
- Target: `ROA`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `12`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 447
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                          crise_covid                0.002130                        0.001832                 0.001830
    2                              estatal                0.000899                        0.000899                 0.000033
    3          captacoes_sobre_ativo_total                0.000626                        0.000597                -0.000335
    4                            crise_nme                0.000562                        0.000560                 0.000560
    5 operacoes_de_credito_sobre_captacoes                0.000553                        0.000519                -0.000223
    6               indice_de_imobilizacao                0.000418                        0.000366                -0.000044
    7               ativos_sobre_depositos                0.000405                        0.000271                -0.000124
    8  depositos_a_prazo_sobre_ativo_total                0.000399                        0.000348                 0.000037
    9  depositos_a_vista_sobre_ativo_total                0.000340                        0.000252                -0.000053
   10                    liquidez_imediata                0.000329                        0.000243                 0.000059
   11                             nsfr_dec                0.000260                        0.000219                -0.000057
   12                              lcr_dec                0.000239                        0.000152                 0.000024
   13     disponibilidades_sobre_depositos                0.000201                        0.000122                 0.000008
   14                 controle_estrangeiro                0.000189                        0.000180                 0.000031
```

## Importância por defasagem
```
 rank  lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1    t                    0.001336               -0.000092
    2  t-1                    0.000879               -0.000048
    3  t-2                    0.000793                0.000047
    4  t-3                    0.000739                0.000129
    5  t-4                    0.000671                0.000203
    6  t-5                    0.000621                0.000248
    7  t-6                    0.000573                0.000263
    8  t-7                    0.000501                0.000246
    9  t-8                    0.000442                0.000234
   10  t-9                    0.000391                0.000209
   11 t-10                    0.000326                0.000174
   12 t-11                    0.000277                0.000134
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

Tempo total de execução: 124.10 segundos.