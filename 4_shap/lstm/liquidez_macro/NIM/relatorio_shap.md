# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_macro/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_macro/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
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
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                    pib_indice_sa_log                0.010570                        0.010570                -0.010570
    2  depositos_a_prazo_sobre_ativo_total                0.004356                        0.004354                 0.000237
    3                              estatal                0.003940                        0.003927                 0.000282
    4                    liquidez_imediata                0.003762                        0.003735                -0.001037
    5                             nsfr_dec                0.003388                        0.003361                 0.000306
    6                          crise_covid                0.003332                        0.002189                 0.000056
    7               ipca_fim_trimestre_dec                0.003036                        0.001743                 0.001564
    8          captacoes_sobre_ativo_total                0.002790                        0.002761                -0.000698
    9 operacoes_de_credito_sobre_captacoes                0.002598                        0.002447                -0.000535
   10  depositos_a_vista_sobre_ativo_total                0.002085                        0.002069                 0.000187
   11              selic_fim_trimestre_dec                0.001645                        0.001051                 0.001032
   12               indice_de_imobilizacao                0.001407                        0.001219                 0.000184
   13               ativos_sobre_depositos                0.001381                        0.001348                 0.000644
   14     disponibilidades_sobre_depositos                0.001246                        0.001202                 0.000992
   15                 controle_estrangeiro                0.000993                        0.000988                -0.000362
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.014352               -0.003776
    2 t-1                    0.009454               -0.000892
    3 t-2                    0.007423               -0.000866
    4 t-3                    0.006416               -0.000642
    5 t-4                    0.005491               -0.000552
    6 t-5                    0.004621               -0.000507
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

Tempo total de execução: 63.86 segundos.