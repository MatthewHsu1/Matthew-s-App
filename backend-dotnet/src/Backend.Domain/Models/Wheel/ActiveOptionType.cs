using System.ComponentModel.DataAnnotations;

namespace Backend.Domain.Models.Wheel
{
    public enum ActiveOptionType
    {
        [Display(Name = "None")]
        None = 0,

        [Display(Name = "Put")]
        Put = 1,

        [Display(Name = "Call")]
        Call = 2
    }
}
