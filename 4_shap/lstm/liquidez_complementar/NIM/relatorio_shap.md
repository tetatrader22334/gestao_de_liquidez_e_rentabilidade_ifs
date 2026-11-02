# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_complementar/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_complementar/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `4`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 559
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1 operacoes_de_credito_sobre_captacoes                0.007032                        0.006160                -0.003137
    2                    liquidez_imediata                0.005890                        0.005882                -0.001702
    3          captacoes_sobre_ativo_total                0.003259                        0.002977                 0.000459
    4               indice_de_imobilizacao                0.002723                        0.002669                 0.000138
    5                             nsfr_dec                0.002533                        0.002468                 0.000369
    6  depositos_a_prazo_sobre_ativo_total                0.002374                        0.002175                -0.001446
    7                              estatal                0.002352                        0.002282                -0.000957
    8     disponibilidades_sobre_depositos                0.002239                        0.001943                -0.000041
    9                          crise_covid                0.002180                        0.001612                -0.000026
   10  depositos_a_vista_sobre_ativo_total                0.002102                        0.001970                 0.000162
   11                              lcr_dec                0.001680                        0.001600                -0.000587
   12                            crise_nme                0.000995                        0.000839                 0.000839
   13               ativos_sobre_depositos                0.000993                        0.000730                 0.000196
   14                 controle_estrangeiro                0.000868                        0.000868                 0.000302
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.013293               -0.001641
    2 t-1                    0.009603               -0.001283
    3 t-2                    0.007749               -0.001371
    4 t-3                    0.006575               -0.001139
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

Tempo total de execução: 77.69 segundos.