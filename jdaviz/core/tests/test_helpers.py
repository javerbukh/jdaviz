import pytest

from astropy import units as u
from glue.core.edit_subset_mode import NewMode
from glue.core.roi import XRangeROI

from jdaviz.core.helpers import _next_subset_num


class MockGroupItem:
    def __init__(self, label):
        self.label = label


@pytest.mark.parametrize(
    ('label', 'prefix', 'answer'),
    [('Subset 1', 'Subset', 2),
     ('Subset 10', 'Subset', 11),
     ('MaskedSubset', 'MaskedSubset', 1),
     ('acs_47tuc_1[SCI,1]', 'acs_47tuc_1[SCI,1]', 1),
     ('acs_47tuc_1[SCI,1] 1', 'acs_47tuc_1[SCI,1]', 2),
     ('asdakdh663 dada233 32432 2', 'asdakdh663', 3),
     ('asdakdh663 dada233 32432 2', 'hmmm', 1),
     ('42 1337 kookookachu', '42', 1)])
def test_next_subset_num(label, prefix, answer):
    mocked_group = [MockGroupItem(label)]
    assert _next_subset_num(prefix, mocked_group) == answer


class TestConfigHelper:
    @pytest.fixture(autouse=True)
    def setup_class(self, specviz_helper, spectrum1d, multi_order_spectrum_list):
        self.spec_app = specviz_helper
        self.spec = spectrum1d
        self.label = "Test 1D Spectrum"

        self.spec2 = spectrum1d._copy(spectral_axis=spectrum1d.spectral_axis+1000*u.AA)
        self.label2 = "Test 1D Spectrum 2"
        self.spec_app.load_spectrum(spectrum1d, data_label=self.label)
        self.spec_app.load_spectrum(self.spec2, data_label=self.label2)

        # Add 3 subsets to cover different parts of spec and spec2
        self.spec_app.app.get_viewer("spectrum-viewer").apply_roi(XRangeROI(6000, 6500))
        self.spec_app.app.session.edit_subset_mode.mode = NewMode

        self.spec_app.app.get_viewer("spectrum-viewer").apply_roi(XRangeROI(6700, 7200))
        self.spec_app.app.get_viewer("spectrum-viewer").apply_roi(XRangeROI(8200, 8800))

    @pytest.mark.parametrize(
        ('label', 'subset_name', 'answer'),
        [('Test 1D Spectrum', 'Subset 1',
          [False, False, False, True, True, True, True, True, True, True]),
         ('Test 1D Spectrum', 'Subset 2',
          [True, True, True, True, False, False, True, True, True, True]),
         ('Test 1D Spectrum', 'Subset 3',
          [True, True, True, True, True, True, True, True, True, True]),
         ('Test 1D Spectrum 2', 'Subset 1',
          [True, True, True, True, True, True, True, True, True, True]),
         ('Test 1D Spectrum 2', 'Subset 2',
          [False, True, True, True, True, True, True, True, True, True]),
         ('Test 1D Spectrum 2', 'Subset 3',
          [True, True, True, True, True, True, False, False, False, True])])
    def test_get_data_with_one_subset_per_data(self, specviz_helper, label, subset_name, answer):

        results = specviz_helper.get_data(data_label=label,
                                          subsets_to_apply=subset_name,
                                          statistic=None)
        assert list(results.mask) == answer
