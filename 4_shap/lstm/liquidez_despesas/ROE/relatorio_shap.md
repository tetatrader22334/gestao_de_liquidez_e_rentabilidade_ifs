# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_despesas/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_despesas/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
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
    1                          crise_covid                0.012465                        0.010880                 0.010845
    2                              estatal                0.007419                        0.006595                -0.000144
    3          despesas_adm_sobre_receitas                0.006515                        0.005277                -0.002386
    4                            crise_nme                0.003980                        0.003980                 0.003980
    5          captacoes_sobre_ativo_total                0.002709                        0.001089                -0.000058
    6  provisao_sobre_operacoes_de_credito                0.002500                        0.001824                -0.000217
    7                 controle_estrangeiro                0.002440                        0.002440                 0.000894
    8                              lcr_dec                0.002274                        0.001168                 0.000436
    9  depositos_a_prazo_sobre_ativo_total                0.002186                        0.001682                -0.000951
   10  depositos_a_vista_sobre_ativo_total                0.002177                        0.001495                -0.000007
   11                    liquidez_imediata                0.001989                        0.001169                 0.000094
   12               indice_de_imobilizacao                0.001705                        0.001579                -0.000566
   13               ativos_sobre_depositos                0.001659                        0.001398                -0.001283
   14 operacoes_de_credito_sobre_captacoes                0.001380                        0.001156                -0.000449
   15                             nsfr_dec                0.001101                        0.000912                -0.000423
```

## Importância por defasagem
```
 rank  lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1    t                    0.006347                0.000102
    2  t-4                    0.005371                0.000911
    3  t-5                    0.005224                0.001197
    4  t-3                    0.005170                0.000385
    5  t-6                    0.005022                0.001372
    6  t-2                    0.004609                0.000013
    7  t-7                    0.004496                0.001220
    8  t-8                    0.004069                0.001176
    9  t-9                    0.003616                0.001242
   10  t-1                    0.003345               -0.000043
   11 t-10                    0.003196                0.001133
   12 t-11                    0.002776                0.000979
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

Tempo total de execução: 142.88 segundos.